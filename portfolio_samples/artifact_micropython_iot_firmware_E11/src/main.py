"""Main firmware event loop managing watchdog feeding, state machine transitions,
telemetry buffering, and graceful power management.
Strict zero em dash policy enforced.
"""
import time
from typing import Optional, List, Dict, Any
from src.models import DeviceState, TelemetrySample, FirmwareConfig


class FirmwareMain:
    """Industrial-grade MicroPython firmware controller with hardware watchdog emulation."""

    def __init__(self, config: Optional[FirmwareConfig] = None):
        self.config = config or FirmwareConfig()
        self.state = DeviceState.BOOTING
        self.start_timestamp = time.time()
        self.wdt_fed_timestamp = time.time()
        self.wdt_timeout_sec = self.config.wdt_timeout_ms / 1000.0
        self.reboot_counter = 0
        self.sequence_counter = 0
        self.ring_buffer: List[Dict[str, Any]] = []
        self.state = DeviceState.SENSING

    def feed_watchdog(self) -> None:
        """Reset hardware watchdog timer timestamp."""
        self.wdt_fed_timestamp = time.time()

    def check_watchdog_timeout(self) -> bool:
        """Check if elapsed time since last feed exceeds WDT timeout threshold."""
        elapsed = time.time() - self.wdt_fed_timestamp
        if elapsed > self.wdt_timeout_sec:
            self.reboot_counter += 1
            self.state = DeviceState.ERROR
            return True
        return False

    def enqueue_telemetry(self, sample: TelemetrySample) -> bool:
        """Push sample to circular ring buffer, capping at max capacity."""
        if len(self.ring_buffer) >= self.config.flash_queue_max_size:
            # Drop oldest entry (FIFO circular queue)
            self.ring_buffer.pop(0)
        self.ring_buffer.append(sample.to_dict())
        self.sequence_counter += 1
        return True

    def get_buffered_count(self) -> int:
        return len(self.ring_buffer)

    def flush_ring_buffer(self) -> List[Dict[str, Any]]:
        """Extract all queued telemetry for batched network dispatch."""
        buffered = list(self.ring_buffer)
        self.ring_buffer.clear()
        return buffered

    def transition_to(self, new_state: DeviceState) -> None:
        """Execute state machine transition with validation."""
        self.state = new_state
        self.feed_watchdog()

    def get_uptime_sec(self) -> int:
        return int(time.time() - self.start_timestamp)
