"""SQLite WAL state manager for GraphQL pagination cursors and idempotency."""
import sqlite3
from typing import Optional


class SyncStateStore:
    """Windows 10 handle-safe SQLite WAL state store for synchronization checkpoints

    and mutation idempotency tracking.
    """

    def __init__(self, db_path: str = "catalog_sync_state.db"):
        self.db_path = db_path
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=5000;")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sync_checkpoints (
                        checkpoint_key TEXT PRIMARY KEY,
                        end_cursor TEXT,
                        has_next_page INTEGER,
                        records_processed INTEGER,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS idempotency_keys (
                        idempotency_key TEXT PRIMARY KEY,
                        payload_hash TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
        finally:
            conn.close()

    def save_cursor(
        self,
        key: str,
        cursor: Optional[str],
        has_next_page: bool,
        processed_count: int,
    ) -> None:
        """Save or update pagination cursor checkpoint atomically."""
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO sync_checkpoints (checkpoint_key, end_cursor, has_next_page, records_processed, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(checkpoint_key) DO UPDATE SET
                        end_cursor=excluded.end_cursor,
                        has_next_page=excluded.has_next_page,
                        records_processed=excluded.records_processed,
                        updated_at=CURRENT_TIMESTAMP;
                    """,
                    (key, cursor, 1 if has_next_page else 0, processed_count),
                )
        finally:
            conn.close()

    def get_cursor(self, key: str) -> Optional[str]:
        """Retrieve stored pagination cursor for checkpoint key."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT end_cursor FROM sync_checkpoints WHERE checkpoint_key = ?",
                (key,),
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def record_idempotency_key(self, key: str, payload_hash: str) -> bool:
        """Atomically record idempotency key.

        Returns True if inserted cleanly, False if key already exists.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            try:
                with conn:
                    conn.execute(
                        "INSERT INTO idempotency_keys (idempotency_key, payload_hash) VALUES (?, ?);",
                        (key, payload_hash),
                    )
                    return True
            except sqlite3.IntegrityError:
                return False
        finally:
            conn.close()

    def has_idempotency_key(self, key: str) -> bool:
        """Check if an idempotency key exists without inserting."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM idempotency_keys WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            return row is not None
        finally:
            conn.close()
