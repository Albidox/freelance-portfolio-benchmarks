"""Dynamic PostgreSQL 18 schema loader (e14_pc_cleanup) on port 5433 with execution logging.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from src.config import WindowsOptimizerConfig
from src.models import CleanupResult, SystemHealthSnapshot


class DatabaseManager:
    """Manages PostgreSQL 18 connections, dynamic schema loading, and execution logging."""

    def __init__(self, config: Optional[WindowsOptimizerConfig] = None):
        self.config = config or WindowsOptimizerConfig()
        self._conn = None

    def get_connection(self):
        """Get or establish connection to PostgreSQL 18 on port 5433."""
        if self._conn is None or self._conn.closed != 0:
            self._conn = psycopg2.connect(
                host=self.config.pg_host,
                port=self.config.pg_port,
                user=self.config.pg_user,
                password=self.config.pg_password,
                dbname=self.config.pg_database,
                connect_timeout=3
            )
            self._conn.autocommit = True
        return self._conn

    def init_schema(self) -> bool:
        """Create e14_pc_cleanup schema and audit tables."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.config.pg_schema};")
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.cleanup_audits (
                        id BIGSERIAL PRIMARY KEY,
                        target_type VARCHAR(64) NOT NULL,
                        target_path TEXT NOT NULL,
                        files_deleted INT NOT NULL,
                        bytes_reclaimed BIGINT NOT NULL,
                        locked_skipped INT NOT NULL DEFAULT 0,
                        executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.health_snapshots (
                        id BIGSERIAL PRIMARY KEY,
                        cpu_usage_pct REAL NOT NULL,
                        ram_percent REAL NOT NULL,
                        disk_free_gb REAL NOT NULL,
                        health_score INT NOT NULL,
                        captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.service_tunings (
                        id BIGSERIAL PRIMARY KEY,
                        service_name VARCHAR(128) NOT NULL,
                        previous_startup VARCHAR(32) NOT NULL,
                        new_startup VARCHAR(32) NOT NULL,
                        reason TEXT NOT NULL,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
            return True
        except Exception:
            return False

    def log_cleanup(
        self,
        target_type: str,
        target_path: str,
        files_deleted: int,
        bytes_reclaimed: int,
        locked_skipped: int = 0
    ) -> bool:
        """Insert disk cleanup execution record into PostgreSQL 18."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.pg_schema}.cleanup_audits
                    (target_type, target_path, files_deleted, bytes_reclaimed, locked_skipped)
                    VALUES (%s, %s, %s, %s, %s);
                """, (target_type, target_path, files_deleted, bytes_reclaimed, locked_skipped))
            return True
        except Exception:
            return False

    def log_health(
        self,
        cpu_usage_pct: float,
        ram_percent: float,
        disk_free_gb: float,
        health_score: int
    ) -> bool:
        """Insert system health snapshot into PostgreSQL 18."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.pg_schema}.health_snapshots
                    (cpu_usage_pct, ram_percent, disk_free_gb, health_score)
                    VALUES (%s, %s, %s, %s);
                """, (cpu_usage_pct, ram_percent, disk_free_gb, health_score))
            return True
        except Exception:
            return False

    def log_service_tuning(
        self,
        service_name: str,
        previous_startup: str,
        new_startup: str,
        reason: str
    ) -> bool:
        """Insert service optimization action into PostgreSQL 18."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.pg_schema}.service_tunings
                    (service_name, previous_startup, new_startup, reason)
                    VALUES (%s, %s, %s, %s);
                """, (service_name, previous_startup, new_startup, reason))
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Close PostgreSQL connection."""
        if self._conn and self._conn.closed == 0:
            self._conn.close()
            self._conn = None
