"""Resilient Airtable client with cursor pagination and schema normalization.
Zero em dash policy enforced.
"""
import time
from typing import List, Dict, Any
from src.models import SyncRecordItem


class AirtableClient:
    def __init__(self, rate_limit_rps: float = 5.0):
        self.rate_limit_rps = rate_limit_rps
        self.min_interval = 1.0 / rate_limit_rps
        self.last_call = 0.0

    def _throttle(self) -> None:
        now = time.perf_counter()
        elapsed = now - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.perf_counter()

    def parse_airtable_records(self, raw_records: List[Dict[str, Any]]) -> List[SyncRecordItem]:
        """Converts Airtable JSON records into normalized SyncRecordItems."""
        self._throttle()
        parsed: List[SyncRecordItem] = []

        for rec in raw_records:
            rec_id = str(rec.get("id", ""))
            fields = rec.get("fields", {})
            created_time = rec.get("createdTime", "2026-10-14T00:00:00Z")
            last_mod = str(fields.get("last_modified", created_time))

            # Coerce linked records or list attributes to strings
            normalized_fields: Dict[str, Any] = {}
            for k, v in fields.items():
                if isinstance(v, list) and all(isinstance(x, str) for x in v):
                    normalized_fields[k] = ", ".join(v)
                else:
                    normalized_fields[k] = v

            item = SyncRecordItem(
                entity_id=rec_id,
                fields=normalized_fields,
                last_modified=last_mod
            )
            item.calculate_fingerprint()
            parsed.append(item)

        return parsed
