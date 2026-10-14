"""Subprocess wrapper for ADB CLI, device heartbeat checker, and gesture executor.
Enforces zero em dash policy.
"""
import subprocess
import time
from typing import Tuple, List, Optional
from src.models import DeviceState, Point
from src.config import ADBBotConfig


class ADBController:
    """Subprocess controller managing ADB interactions with mobile devices."""

    def __init__(self, config: ADBBotConfig):
        self.config = config
        self.reconnect_attempts: int = 0
        self.device_state: DeviceState = DeviceState.DISCONNECTED

    def parse_device_list(self, output_text: str) -> List[Tuple[str, str]]:
        """Parse raw stdout from 'adb devices' into serial and state pairs."""
        lines = [line.strip() for line in output_text.splitlines() if line.strip()]
        devices: List[Tuple[str, str]] = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 2:
                devices.append((parts[0], parts[1]))
        return devices

    def check_connection(self, simulated_output: Optional[str] = None) -> DeviceState:
        """Query connected ADB device status."""
        if simulated_output is not None:
            raw = simulated_output
        else:
            try:
                res = subprocess.run(
                    [self.config.adb_path, "devices"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                raw = res.stdout
            except Exception:
                self.device_state = DeviceState.DISCONNECTED
                return self.device_state

        devs = self.parse_device_list(raw)
        for serial, state in devs:
            if serial == self.config.device_serial or self.config.device_serial == "":
                if state == "device":
                    self.device_state = DeviceState.CONNECTED
                    self.reconnect_attempts = 0
                    return self.device_state
                elif state == "offline":
                    self.device_state = DeviceState.OFFLINE
                    return self.device_state
                elif state == "unauthorized":
                    self.device_state = DeviceState.UNAUTHORIZED
                    return self.device_state

        self.device_state = DeviceState.DISCONNECTED
        return self.device_state

    def build_tap_command(self, point: Point) -> List[str]:
        """Build argument vector for adb shell input tap."""
        return [
            self.config.adb_path,
            "-s", self.config.device_serial,
            "shell", "input", "tap",
            str(point.x), str(point.y)
        ]

    def build_swipe_command(self, start: Point, end: Point, duration_ms: int = 300) -> List[str]:
        """Build argument vector for adb shell input swipe."""
        return [
            self.config.adb_path,
            "-s", self.config.device_serial,
            "shell", "input", "swipe",
            str(start.x), str(start.y),
            str(end.x), str(end.y),
            str(duration_ms)
        ]

    def build_text_command(self, text: str) -> List[str]:
        """Build argument vector for adb shell input text."""
        escaped = text.replace(" ", "%s")
        return [
            self.config.adb_path,
            "-s", self.config.device_serial,
            "shell", "input", "text",
            escaped
        ]

    def build_keyevent_command(self, key_code: int) -> List[str]:
        """Build argument vector for adb shell input keyevent."""
        return [
            self.config.adb_path,
            "-s", self.config.device_serial,
            "shell", "input", "keyevent",
            str(key_code)
        ]

    def execute_command(self, cmd: List[str], timeout: float = 10.0) -> Tuple[bool, str, str]:
        """Execute ADB subprocess command with timeout guard."""
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return (res.returncode == 0, res.stdout, res.stderr)
        except subprocess.TimeoutExpired:
            return (False, "", f"Command timed out after {timeout}s")
        except Exception as e:
            return (False, "", str(e))

    def reconnect_device(self) -> bool:
        """Attempt device reconnection with exponential backoff."""
        if self.reconnect_attempts >= self.config.max_reconnect_attempts:
            return False

        self.reconnect_attempts += 1
        backoff_sec = min(2 ** self.reconnect_attempts * 0.5, 8.0)
        time.sleep(backoff_sec)

        try:
            subprocess.run([self.config.adb_path, "reconnect"], capture_output=True, timeout=5)
            st = self.check_connection()
            return st == DeviceState.CONNECTED
        except Exception:
            return False
