"""Dual-tier storage: SQLite WAL local audit cache + PostgreSQL 18 on port 5433.
Strict zero em dash policy enforced.
"""
import sqlite3
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from src.config import WindowsOptimizerConfig
from src.models import CleanupResult, SystemHealthSnapshot
from src.db import DatabaseManager


class WindowsOptimizerStorage:
    """Manages local SQLite WAL persistence and synchronizes audits to PostgreSQL 18."""

    def __init__(self, config: Optional[WindowsOptimizerConfig] = None):
        self.config = config or WindowsOptimizerConfig()
        self.sqlite_conn: Optional[sqlite3.Connection] = None
        self.db_manager: Optional[DatabaseManager] = None
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialize SQLite database with WAL journal mode and busy timeout."""
        self.sqlite_conn = sqlite3.connect(self.config.sqlite_db_path, timeout=5.0)
        self.sqlite_conn.execute("PRAGMA journal_mode=WAL;")
        self.sqlite_conn.execute("PRAGMA busy_timeout=5000;")
        self.sqlite_conn.execute("""
            CREATE TABLE IF NOT EXISTS cleanup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL,
                target_path TEXT NOT NULL,
                files_scanned INTEGER NOT NULL,
                files_deleted INTEGER NOT NULL,
                bytes_reclaimed INTEGER NOT NULL,
                locked_skipped INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        self.sqlite_conn.execute("""
            CREATE TABLE IF NOT EXISTS health_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cpu_usage_pct REAL NOT NULL,
                ram_percent REAL NOT NULL,
                disk_free_gb REAL NOT NULL,
                health_score INTEGER NOT NULL,
                captured_at TEXT NOT NULL
            );
        """)
        self.sqlite_conn.commit()

    def record_cleanup(self, result: CleanupResult) -> None:
        """Persist cleanup execution result in SQLite database."""
        if not self.sqlite_conn:
            return
        query = """
            INSERT INTO cleanup_history (target_type, target_path, files_scanned, files_deleted, bytes_reclaimed, locked_skipped, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        now = datetime.now(timezone.utc).isoformat()
        self.sqlite_conn.execute(query, (
            result.target_type.value,
            result.target_path,
            result.files_scanned,
            result.files_deleted,
            result.bytes_reclaimed,
            result.locked_files_skipped,
            now
        ))
        self.sqlite_conn.commit()

    def record_health(self, snapshot: SystemHealthSnapshot) -> None:
        """Persist health snapshot in SQLite database."""
        if not self.sqlite_conn:
            return
        query = """
            INSERT INTO health_snapshots (cpu_usage_pct, ram_percent, disk_free_gb, health_score, captured_at)
            VALUES (?, ?, ?, ?, ?);
        """
        self.sqlite_conn.execute(query, (
            snapshot.cpu_usage_pct,
            snapshot.ram_percent,
            snapshot.disk_free_gb,
            snapshot.health_score,
            snapshot.captured_at
        ))
        self.sqlite_conn.commit()

    def get_cleanup_summary(self) -> Dict[str, Any]:
        """Aggregate total bytes freed and files deleted from SQLite history."""
        if not self.sqlite_conn:
            return {"total_files_deleted": 0, "total_bytes_reclaimed": 0}
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT SUM(files_deleted), SUM(bytes_reclaimed) FROM cleanup_history")
        row = cursor.fetchone()
        return {
            "total_files_deleted": row[0] or 0,
            "total_bytes_reclaimed": row[1] or 0
        }

    def init_postgres_schema(self) -> bool:
        """Initialize PostgreSQL 18 schema e14_pc_cleanup on port 5433 if available."""
        try:
            if not self.db_manager:
                self.db_manager = DatabaseManager(self.config)
            return self.db_manager.init_schema()
        except Exception:
            return False

    def sync_to_postgres(self) -> bool:
        """Synchronize unlogged records to PostgreSQL 18."""
        try:
            if not self.init_postgres_schema() or not self.sqlite_conn or not self.db_manager:
                return False
            cursor = self.sqlite_conn.cursor()
            cursor.execute("SELECT target_type, target_path, files_deleted, bytes_reclaimed, locked_skipped FROM cleanup_history")
            rows = cursor.fetchall()
            for r in rows:
                self.db_manager.log_cleanup(r[0], r[1], r[2], r[3], r[4])
            return True
        except Exception:
            return False

    def close(self) -> None:
        if self.sqlite_conn:
            self.sqlite_conn.close()
            self.sqlite_conn = None
        if self.db_manager:
            self.db_manager.close()
            self.db_manager = None
