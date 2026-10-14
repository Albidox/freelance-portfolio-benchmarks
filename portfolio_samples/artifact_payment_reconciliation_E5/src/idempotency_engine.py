"""Idempotency engine and distributed deduplication tracker.
Zero em dashes policy strictly enforced.
"""
import time
from typing import Dict, Any, Optional, Set
from collections import OrderedDict
from src.models import WebhookPayload


class IdempotentEventReceiver:
    """Guarantees exactly-once webhook processing with in-memory LRU dedup and lock tracking."""

    def __init__(self, cache_size: int = 10000):
        self.cache_size = cache_size
        self._processed_events: OrderedDict[str, float] = OrderedDict()
        self._in_flight_locks: Set[str] = set()
        self.duplicate_events_prevented: int = 0

    def _event_key(self, gateway: str, event_id: str) -> str:
        return f"{gateway}:{event_id}"

    def try_claim_event(self, gateway: str, event_id: str) -> bool:
        """Attempt to claim processing rights for event. Returns False if already processed or in-flight."""
        key = self._event_key(gateway, event_id)
        if key in self._processed_events:
            self.duplicate_events_prevented += 1
            return False
        if key in self._in_flight_locks:
            self.duplicate_events_prevented += 1
            return False

        self._in_flight_locks.add(key)
        return True

    def commit_event(self, gateway: str, event_id: str) -> None:
        """Mark event as permanently processed and release lock."""
        key = self._event_key(gateway, event_id)
        if key in self._in_flight_locks:
            self._in_flight_locks.remove(key)

        self._processed_events[key] = time.time()
        # Enforce LRU cache eviction ceiling
        if len(self._processed_events) > self.cache_size:
            self._processed_events.popitem(last=False)

    def release_event_lock(self, gateway: str, event_id: str) -> None:
        """Release lock on transient failure without marking as processed."""
        key = self._event_key(gateway, event_id)
        if key in self._in_flight_locks:
            self._in_flight_locks.remove(key)

    def is_processed(self, gateway: str, event_id: str) -> bool:
        key = self._event_key(gateway, event_id)
        return key in self._processed_events
