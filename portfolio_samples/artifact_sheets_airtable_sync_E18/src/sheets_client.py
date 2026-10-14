"""Resilient Google Sheets client with token-bucket rate limiting and formula guards.
Zero em dash policy enforced.
"""
import time
from typing import List, Dict, Any, Optional
from src.models import SyncRecordItem


class GoogleSheetsClient:
    def __init__(self, rate_limit_rps: float = 5.0, bucket_capacity: int = 10):
        self.rate_limit_rps = rate_limit_rps
        self.capacity = float(bucket_capacity)
        self.tokens = float(bucket_capacity)
        self.last_refill = time.perf_counter()

    def _consume_token(self) -> None:
        """Enforces token-bucket rate limit."""
        now = time.perf_counter()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_limit_rps)
        self.last_refill = now

        if self.tokens < 1.0:
            sleep_needed = (1.0 - self.tokens) / self.rate_limit_rps
            time.sleep(sleep_needed)
            self.tokens = 0.0
        else:
            self.tokens -= 1.0

    def parse_sheet_rows(self, raw_rows: List[List[Any]], headers: List[str]) -> List[SyncRecordItem]:
        """Converts raw 2D sheet array into structured SyncRecordItems, preserving formulas."""
        self._consume_token()
        records: List[SyncRecordItem] = []

        for row_idx, row in enumerate(raw_rows):
            fields: Dict[str, Any] = {}
            formulas: Dict[str, str] = {}
            entity_id = ""

            for col_idx, header in enumerate(headers):
                val = row[col_idx] if col_idx < len(row) else None
                if isinstance(val, str) and val.startswith("="):
                    formulas[header] = val
                    fields[header] = val
                else:
                    fields[header] = val

                if header.lower() in ("id", "record_id", "entity_id") and val:
                    entity_id = str(val)

            if not entity_id:
                entity_id = f"sheet_row_{row_idx + 1}"

            last_mod = str(fields.get("last_modified", "2026-10-14T00:00:00Z"))
            rec = SyncRecordItem(
                entity_id=entity_id,
                fields=fields,
                last_modified=last_mod,
                formula_fields=formulas
            )
            rec.calculate_fingerprint()
            records.append(rec)

        return records
