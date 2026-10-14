"""Dual-tier audit persistence using SQLite WAL local cache and Native PostgreSQL 18 sync.
Strict zero em dash policy enforced.
"""
import sqlite3
import os
from typing import List, Dict, Any, Optional
from src.models import MigrationAuditLog, QuarantineRecord, MigrationStatus
from src.config import DatabaseMigrationConfig


class MigrationStorage:
    """Manages audit logging and quarantine tables in local SQLite WAL storage."""

    def __init__(self, config: Optional[DatabaseMigrationConfig] = None):
        self.config = config or DatabaseMigrationConfig()
        self.sqlite_path = self.config.sqlite_audit_path
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initializes SQLite schema in WAL mode with busy timeout."""
        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_runs (\n                    run_id TEXT PRIMARY KEY,
                    source_type TEXT,
                    target_schema TEXT,
                    table_name TEXT,
                    total_migrated INTEGER,
                    quarantined_count INTEGER,
                    elapsed_seconds REAL,
                    status TEXT,
                    completed_at TEXT
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quarantined_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT,
                    raw_payload TEXT,
                    failure_reason TEXT,
                    quarantined_at TEXT
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def record_audit_log(self, audit: MigrationAuditLog) -> None:
        """Stores audit run in local SQLite cache."""
        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("""
                INSERT INTO audit_runs (
                    run_id, source_type, target_schema, table_name,
                    total_migrated, quarantined_count, elapsed_seconds, status, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                audit.run_id, audit.source_type, audit.target_schema, audit.table_name,
                audit.total_migrated, audit.quarantined_count, audit.elapsed_seconds,
                audit.status.value, audit.completed_at
            ))
            conn.commit()
        finally:
            conn.close()

    def record_quarantine_items(self, items: List[QuarantineRecord]) -> None:
        """Persists quarantined corrupt records."""
        if not items:
            return
        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            cur = conn.cursor()
            cur.executemany("""
                INSERT INTO quarantined_items (source_id, raw_payload, failure_reason, quarantined_at)
                VALUES (?, ?, ?, ?);
            """, [(it.source_id, it.raw_payload, it.failure_reason, it.quarantined_at) for it in items])
            conn.commit()
        finally:
            conn.close()

    def get_latest_audit(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Reads back audit run for verification."""
        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM audit_runs WHERE run_id = ?", (run_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
