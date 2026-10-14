"""Token bucket rate limiter modeled after Shopify Admin GraphQL cost points."""
import asyncio
import time
from typing import Optional


class ShopifyRateLimiter:
    """Leaky-bucket / token bucket rate limiter for Shopify Admin GraphQL API.

    Shopify provides a 1,000 cost-point bucket with a restore rate of 50 points per second.
    This limiter manages outbound cost points, tracks throttle status from GraphQL response
    extensions, and calculates exact replenishment pauses to prevent HTTP 429 penalties.
    """

    def __init__(
        self,
        maximum_points: int = 1000,
        restore_rate_per_sec: int = 50,
        initial_points: Optional[int] = None,
    ):
        self.maximum_points = maximum_points
        self.restore_rate_per_sec = restore_rate_per_sec
        self.current_points = float(initial_points if initial_points is not None else maximum_points)
        self.last_leak_time = time.monotonic()
        self._lock = asyncio.Lock()

    def _replenish(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_leak_time
        replenished = elapsed * self.restore_rate_per_sec
        self.current_points = min(float(self.maximum_points), self.current_points + replenished)
        self.last_leak_time = now

    @property
    def available_points(self) -> int:
        self._replenish()
        return int(self.current_points)

    async def acquire(self, requested_cost: int = 10) -> float:
        """Acquire cost points. If current capacity is insufficient, pause until restored.

        Returns total wait duration in seconds.
        """
        async with self._lock:
            self._replenish()
            wait_time = 0.0
            if self.current_points < requested_cost:
                deficit = requested_cost - self.current_points
                wait_time = deficit / self.restore_rate_per_sec
                await asyncio.sleep(wait_time)
                self._replenish()

            self.current_points = max(0.0, self.current_points - requested_cost)
            return wait_time

    def try_acquire(self, requested_cost: int = 10) -> bool:
        """Non-blocking attempt to acquire cost points."""
        self._replenish()
        if self.current_points >= requested_cost:
            self.current_points -= requested_cost
            return True
        return False

    def update_from_extensions(
        self,
        currently_available: int,
        restore_rate: Optional[int] = None,
        max_available: Optional[int] = None,
    ) -> None:
        """Synchronize bucket state directly from Shopify extensions.cost metadata."""
        self.current_points = float(currently_available)
        if restore_rate is not None:
            self.restore_rate_per_sec = restore_rate
        if max_available is not None:
            self.maximum_points = max_available
        self.last_leak_time = time.monotonic()
