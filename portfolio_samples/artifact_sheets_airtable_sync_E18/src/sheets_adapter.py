"""Google Sheets API adapter with chunked streaming and quota backoff handling.
Zero em dash policy enforced.
"""
import time
import random
from typing import List, Dict, Any, Optional, Iterator
from src.models import SyncRecordItem, SyncBatch
from src.sheets_client import GoogleSheetsClient


class SheetsAdapter(GoogleSheetsClient):
    """Production Google Sheets adapter supporting chunked streaming and quota backoff."""

    def __init__(
        self,
        rate_limit_rps: float = 5.0,
        bucket_capacity: int = 10,
        chunk_size: int = 500,
        max_retries: int = 4
    ):
        super().__init__(rate_limit_rps=rate_limit_rps, bucket_capacity=bucket_capacity)
        self.chunk_size = chunk_size
        self.max_retries = max_retries

    def stream_chunked_records(
        self,
        raw_rows: List[List[Any]],
        headers: List[str]
    ) -> Iterator[List[SyncRecordItem]]:
        """Yields parsed SyncRecordItems in bounded chunks to protect memory."""
        for i in range(0, len(raw_rows), self.chunk_size):
            chunk = raw_rows[i:i + self.chunk_size]
            yield self.parse_sheet_rows_with_backoff(chunk, headers)

    def parse_sheet_rows_with_backoff(
        self,
        raw_rows: List[List[Any]],
        headers: List[str]
    ) -> List[SyncRecordItem]:
        """Parses rows with simulated exponential backoff against API quota errors."""
        retries = 0
        backoff_delay = 0.5

        while True:
            try:
                return self.parse_sheet_rows(raw_rows, headers)
            except Exception as exc:
                retries += 1
                if retries > self.max_retries:
                    raise exc
                jitter = random.uniform(0.05, 0.2)
                time.sleep(backoff_delay + jitter)
                backoff_delay *= 2.0

    def format_records_for_sheet(
        self,
        records: List[SyncRecordItem],
        headers: List[str]
    ) -> List[List[Any]]:
        """Serializes SyncRecordItems into 2D row array, preserving formulas."""
        rows: List[List[Any]] = []
        for rec in records:
            row: List[Any] = []
            for h in headers:
                if h in rec.formula_fields:
                    row.append(rec.formula_fields[h])
                else:
                    row.append(rec.fields.get(h, ""))
            rows.append(row)
        return rows


# Backward compatibility alias
GoogleSheetsAdapter = SheetsAdapter
