"""In-memory leaky bucket and backoff coordinator respecting upstream API quotas
within single execution turns.
Strict zero em dash policy enforced.
"""
import time
import math
import random
from typing import Optional, Tuple


class ServerlessRateLimiter:
    def __init__(self, max_capacity: int = 10, leak_rate_per_sec: float = 2.0):
        self.max_capacity = float(max_capacity)
        self.leak_rate = float(leak_rate_per_sec)
        self.water_level = 0.0
        self.last_leak_time = time.time()
        self.total_throttled = 0

    def _leak(self) -> None:
        """Calculate amount leaked since last check."""
        now = time.time()
        elapsed = now - self.last_leak_time
        leaked = elapsed * self.leak_rate
        self.water_level = max(0.0, self.water_level - leaked)
        self.last_leak_time = now

    def acquire_token(self, tokens: float = 1.0) -> Tuple[bool, float]:
        """Attempt to acquire execution quota. Returns (success, wait_time_seconds)."""
        self._leak()
        if self.water_level + tokens <= self.max_capacity:
            self.water_level += tokens
            return True, 0.0
        else:
            self.total_throttled += 1
            excess = (self.water_level + tokens) - self.max_capacity
            wait_time = excess / self.leak_rate if self.leak_rate > 0 else 1.0
            return False, round(wait_time, 3)

    def calculate_backoff(self, attempt: int, base_delay: float = 0.5, max_delay: float = 5.0, jitter_factor: float = 0.2) -> float:
        """Calculate exponential backoff with jitter, capped at max_delay."""
        raw_delay = base_delay * (2 ** attempt)
        jitter = random.uniform(0.0, jitter_factor * raw_delay)
        delay = min(raw_delay + jitter, max_delay)
        return round(delay, 3)

    def parse_retry_after(self, retry_header: Optional[str], default_delay: float = 2.0) -> float:
        """Parse HTTP Retry-After header (seconds integer or float)."""
        if not retry_header:
            return default_delay
        try:
            val = float(retry_header.strip())
            return max(0.1, min(val, 10.0))
        except ValueError:
            return default_delay
