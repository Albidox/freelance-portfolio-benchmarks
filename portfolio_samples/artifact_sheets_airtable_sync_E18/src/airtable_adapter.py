"""Airtable REST API client handling rate-limiting (5 rps) and batch upserts.
Zero em dash policy enforced.
"""
import time
from typing import List, Dict, Any, Optional
from src.models import SyncRecordItem, SyncBatch
from src.airtable_client import AirtableClient


class AirtableAdapter(AirtableClient):
    """Production Airtable adapter supporting rate limiting (5 rps) and batch upserts."""

    def __init__(self, rate_limit_rps: float = 5.0, batch_size: int = 10):
        super().__init__(rate_limit_rps=rate_limit_rps)
        self.batch_size = min(batch_size, 10)  # Airtable API caps batch requests at 10

    def prepare_batch_upsert_payloads(
        self,
        records: List[SyncRecordItem],
        typecast: bool = True
    ) -> List[Dict[str, Any]]:
        """Splits records into Airtable batch upsert payloads (max 10 records per request)."""
        batches: List[Dict[str, Any]] = []
        for i in range(0, len(records), self.batch_size):
            chunk = records[i:i + self.batch_size]
            payload_records = []
            for r in chunk:
                item_dict: Dict[str, Any] = {
                    "fields": {k: v for k, v in r.fields.items() if k != "id"}
                }
                if r.entity_id and not r.entity_id.startswith("sheet_row_"):
                    item_dict["id"] = r.entity_id
                payload_records.append(item_dict)

            batches.append({
                "records": payload_records,
                "typecast": typecast
            })
        return batches

    def execute_batch_upsert_simulation(
        self,
        records: List[SyncRecordItem]
    ) -> Dict[str, Any]:
        """Simulates executing rate-limited batch upserts against Airtable REST API."""
        payloads = self.prepare_batch_upsert_payloads(records)
        processed_count = 0
        t0 = time.perf_counter()

        for payload in payloads:
            self._throttle()
            processed_count += len(payload["records"])

        elapsed = time.perf_counter() - t0
        return {
            "total_records": processed_count,
            "batches_executed": len(payloads),
            "elapsed_seconds": round(elapsed, 4),
            "effective_rps": round(processed_count / elapsed, 2) if elapsed > 0 else 0.0
        }


# Compatibility alias
AirtableClientAdapter = AirtableAdapter
