"""Background service worker logic, message dispatcher, and cloud sync coordinator."""
import time
from typing import Dict, Any, Tuple, Optional, List
from collections import deque


class BackgroundServiceWorker:
    def __init__(self, max_queue_size: int = 10000):
        self.max_queue_size = max_queue_size
        self.message_handlers: Dict[str, Any] = {}
        self.sync_queue: deque = deque(maxlen=max_queue_size)
        self.consecutive_sync_failures: int = 0
        self.base_backoff_seconds: float = 1.0
        self.sync_backoff_seconds: float = 1.0
        self.alarms: Dict[str, float] = {}

    def handle_message(self, message: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Route internal Chrome extension messages between popup and content scripts."""
        action = message.get("action", "")
        payload = message.get("payload", {})

        if action == "PING":
            return True, {"status": "PONG", "timestamp": time.time()}

        if action == "QUEUE_EXPORT_BATCH":
            records = payload.get("records", [])
            for r in records:
                self.sync_queue.append(r)
            return True, {"queued_count": len(records), "total_in_queue": len(self.sync_queue)}

        if action == "GET_QUEUE_STATUS":
            return True, {"queue_depth": len(self.sync_queue), "backoff_seconds": self.sync_backoff_seconds}

        return False, {"error": f"Unknown action: {action}"}

    def calculate_exponential_backoff(self, status_code: int) -> float:
        """Calculate exponential backoff delay with jitter cap for HTTP 429/503 errors."""
        if status_code in [429, 503]:
            self.consecutive_sync_failures += 1
            delay = min(60.0, self.base_backoff_seconds * (2 ** (self.consecutive_sync_failures - 1)))
            self.sync_backoff_seconds = delay
            return delay
        self.consecutive_sync_failures = 0
        self.sync_backoff_seconds = self.base_backoff_seconds
        return 0.0

    def schedule_alarm(self, alarm_name: str, delay_seconds: float) -> None:
        """Schedule chrome.alarms wake-up callback."""
        self.alarms[alarm_name] = time.time() + delay_seconds
