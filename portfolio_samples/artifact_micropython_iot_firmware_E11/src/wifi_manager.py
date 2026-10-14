"""WiFi station manager with exponential backoff, static IP fallback, and captive portal support.
Strict zero em dash policy enforced.
"""
import time
import math
import random
from typing import Dict, Any, Optional
from src.models import NetworkConfig, NetworkTelemetryRecord


class WiFiManager:
    """Non-blocking Wi-Fi station manager with exponential backoff and captive portal fallback."""

    def __init__(self, ssid: str = "IoT_Net", fallback_static_ip: str = "192.168.1.150"):
        self.ssid = ssid
        self.fallback_static_ip = fallback_static_ip
        self.is_connected = False
        self.current_ip: Optional[str] = None
        self.rssi_dbm = -65
        self.reconnect_attempts = 0
        self.static_fallback_activated = False
        self.captive_portal_active = False
        self.dropped_packets = 0
        self.connected_since: Optional[float] = None

    def calculate_reconnect_delay(
        self,
        attempt: int,
        base_sec: float = 1.0,
        max_sec: float = 30.0,
        jitter_factor: float = 0.25
    ) -> float:
        """Calculate exponential backoff delay with random jitter."""
        raw = base_sec * (2 ** min(attempt, 6))
        jitter = random.uniform(0.0, jitter_factor * raw)
        return round(min(raw + jitter, max_sec), 2)

    def connect(self, simulate_dhcp_fail: bool = False, simulate_offline: bool = False) -> bool:
        """Execute Wi-Fi connection handshake with DHCP or static IP fallback."""
        self.reconnect_attempts += 1
        if simulate_offline:
            self.is_connected = False
            self.current_ip = None
            self.connected_since = None
            if self.reconnect_attempts >= 3:
                self.start_captive_portal()
            return False

        if simulate_dhcp_fail:
            # Fallback to static IP configuration
            self.static_fallback_activated = True
            self.current_ip = self.fallback_static_ip
            self.is_connected = True
            self.rssi_dbm = -70
            self.connected_since = time.time()
            self.stop_captive_portal()
            return True

        self.static_fallback_activated = False
        self.current_ip = "192.168.1.105"
        self.is_connected = True
        self.rssi_dbm = -58
        self.connected_since = time.time()
        self.stop_captive_portal()
        return True

    def disconnect(self) -> None:
        """Tear down active station link."""
        self.is_connected = False
        self.current_ip = None
        self.connected_since = None

    def check_link_health(self) -> bool:
        """Verify network interface state and link signal quality."""
        if not self.is_connected:
            return False
        if self.rssi_dbm < -90:
            # Weak or unusable link
            return False
        return True

    def start_captive_portal(self) -> bool:
        """Activate AP mode fallback for manual network provisioning."""
        self.captive_portal_active = True
        return True

    def stop_captive_portal(self) -> None:
        """Deactivate captive portal AP mode."""
        self.captive_portal_active = False

    def get_network_telemetry(self) -> NetworkTelemetryRecord:
        """Compile network telemetry record."""
        uptime = int(time.time() - self.connected_since) if self.connected_since else 0
        return NetworkTelemetryRecord(
            rssi_dbm=self.rssi_dbm,
            ip_address=self.current_ip or "0.0.0.0",
            reconnect_count=self.reconnect_attempts,
            dropped_packets=self.dropped_packets,
            uptime_seconds=uptime,
        )
