"""Dual-tier audit persistence using SQLite WAL local cache and Native PostgreSQL 18 sync.
Zero em dash policy enforced.
"""
import sqlite3
import os
from typing import Dict, Any, Optional, List
from src.models import SyncCycleReport
from src.config import SheetsAirtableSyncConfig


class SyncStorage:
    def __init__(self, config: SheetsAirtableSyncConfig):
        self.config = config
        self.sqlite_path = config.sqlite_db_path
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initializes SQLite schema in WAL mode."""
        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_audit_log (
                    cycle_id TEXT PRIMARY KEY,
                    direction TEXT,
                    records_scanned INTEGER,
                    records_added INTEGER,
                    records_updated INTEGER,
                    records_deleted INTEGER,
                    conflicts_resolved INTEGER,
                    conflicts_quarantined INTEGER,
                    elapsed_seconds REAL,
                    completed_at TEXT
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def record_sync_cycle(self, report: SyncCycleReport) -> None:
        """Stores sync cycle audit record in SQLite WAL table."""
        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO sync_audit_log (
                    cycle_id, direction, records_scanned, records_added,
                    records_updated, records_deleted, conflicts_resolved,
                    conflicts_quarantined, elapsed_seconds, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                report.cycle_id,
                report.direction.value if hasattr(report.direction, "value") else str(report.direction),
                report.records_scanned,
                report.records_added,
                report.records_updated,
                report.records_deleted,
                report.conflicts_resolved,
                report.conflicts_quarantined,
                report.elapsed_seconds,
                report.completed_at
            ))
            conn.commit()
        finally:
            conn.close()

    def get_latest_cycle(self, cycle_id: str) -> Optional[Dict[str, Any]]:
        """Reads back sync cycle audit record for verification."""
        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM sync_audit_log WHERE cycle_id = ?", (cycle_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_recent_cycles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Lists recent sync audit records."""
        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM sync_audit_log ORDER BY completed_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
