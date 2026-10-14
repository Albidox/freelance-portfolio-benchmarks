"""Streaming cursor extractor with deterministic batching and checkpoint recovery.
Strict zero em dash policy enforced.
"""
import sqlite3
import time
from typing import List, Dict, Any, Generator, Optional
from src.models import MigrationRecord, MigrationBatch, MigrationSourceType
from src.config import DatabaseMigrationConfig


class SourceExtractor:
    """Streams records in deterministic batch chunks with simulated cursor pagination."""

    def __init__(self, config: Optional[DatabaseMigrationConfig] = None):
        self.config = config or DatabaseMigrationConfig()
        self.last_checkpoint_offset = 0
        self.total_extracted = 0

    def stream_records_from_dataset(
        self,
        table_name: str,
        dataset: List[Dict[str, Any]],
        start_offset: int = 0,
        batch_size: Optional[int] = None
    ) -> Generator[MigrationBatch, None, None]:
        """Streams records in deterministic batch chunks with simulated cursor pagination."""
        chunk_size = batch_size or self.config.batch_size
        current_offset = start_offset
        batch_id = 1
        total_rows = len(dataset)

        while current_offset < total_rows:
            chunk = dataset[current_offset:current_offset + chunk_size]
            records: List[MigrationRecord] = []
            for idx, raw_row in enumerate(chunk):
                source_id = str(raw_row.get("id", f"row_{current_offset + idx}"))
                rec = MigrationRecord(source_id=source_id, data=raw_row)
                rec.calculate_checksum()
                records.append(rec)

            batch = MigrationBatch(
                batch_id=batch_id,
                source_type=MigrationSourceType(self.config.source_type),
                table_name=table_name,
                records=records,
                start_offset=current_offset,
                end_offset=current_offset + len(records)
            )

            current_offset += len(records)
            self.last_checkpoint_offset = current_offset
            self.total_extracted += len(records)
            batch_id += 1

            yield batch

    def simulate_network_interruption(self, interrupt_after_offset: int, current_offset: int) -> bool:
        """Determines if a transient network socket timeout occurred."""
        if current_offset >= interrupt_after_offset:
            return True
        return False

    def save_checkpoint_offset(self, db_path: str, table_name: str, offset: int) -> None:
        """Stores migration progress bookmark in SQLite WAL table."""
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS migration_checkpoints (
                    table_name TEXT PRIMARY KEY,
                    offset_marker INTEGER NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                INSERT INTO migration_checkpoints (table_name, offset_marker, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(table_name) DO UPDATE SET
                    offset_marker=excluded.offset_marker,
                    updated_at=excluded.updated_at;
            """, (table_name, offset))
            conn.commit()
        finally:
            conn.close()

    def load_checkpoint_offset(self, db_path: str, table_name: str) -> int:
        """Retrieves last committed offset to resume streaming."""
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT offset_marker FROM migration_checkpoints WHERE table_name = ?", (table_name,))
            row = cur.fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()
