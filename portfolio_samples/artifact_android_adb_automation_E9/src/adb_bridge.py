"""Async ADB Bridge executing input commands with subprocess guards and recovery.
Enforces zero em dash policy.
"""
import asyncio
import subprocess
from typing import Optional, List, Tuple
from src.models import Point, DeviceState
from src.config import ADBBotConfig
from src.adb_controller import ADBController


class AsyncADBBridge:
    """Asynchronous ADB bridge with non-blocking subprocess execution and auto-recovery."""

    def __init__(self, config: Optional[ADBBotConfig] = None):
        self.config = config or ADBBotConfig()
        self.controller = ADBController(self.config)
        self.lock = asyncio.Lock()
        self.consecutive_failures: int = 0

    async def execute_async_command(
        self,
        args: List[str],
        timeout: float = 5.0
    ) -> Tuple[bool, str, str]:
        """Execute command asynchronously with strict timeout guard."""
        async with self.lock:
            proc = None
            try:
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout_data, stderr_data = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
                stdout_str = stdout_data.decode("utf-8", errors="replace")
                stderr_str = stderr_data.decode("utf-8", errors="replace")
                success = (proc.returncode == 0)

                if success:
                    self.consecutive_failures = 0
                else:
                    self.consecutive_failures += 1

                return (success, stdout_str, stderr_str)
            except asyncio.TimeoutError:
                self.consecutive_failures += 1
                if proc is not None:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                return (False, "", f"Async command timed out after {timeout} seconds")
            except Exception as e:
                self.consecutive_failures += 1
                return (False, "", str(e))

    async def tap(self, point: Point, timeout: float = 5.0) -> bool:
        """Execute asynchronous touch tap at specified coordinates."""
        cmd = self.controller.build_tap_command(point)
        success, _, _ = await self.execute_async_command(cmd, timeout=timeout)
        if not success and self.consecutive_failures >= 2:
            await self.recover_connection()
        return success

    async def swipe(
        self,
        start: Point,
        end: Point,
        duration_ms: int = 300,
        timeout: float = 5.0
    ) -> bool:
        """Execute asynchronous touch swipe gesture between points."""
        cmd = self.controller.build_swipe_command(start, end, duration_ms)
        success, _, _ = await self.execute_async_command(cmd, timeout=timeout)
        if not success and self.consecutive_failures >= 2:
            await self.recover_connection()
        return success

    async def input_text(self, text: str, timeout: float = 5.0) -> bool:
        """Execute asynchronous text input with space escaping."""
        cmd = self.controller.build_text_command(text)
        success, _, _ = await self.execute_async_command(cmd, timeout=timeout)
        return success

    async def check_device_state(self) -> DeviceState:
        """Asynchronously query device state."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.controller.check_connection)

    async def recover_connection(self) -> bool:
        """Trigger device reconnect and verify recovery."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.controller.reconnect_device)
