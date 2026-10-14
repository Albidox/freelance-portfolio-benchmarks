"""Dual-tier storage: SQLite WAL local audit cache + Native PostgreSQL 18 on port 5433.
Strict zero em dash policy enforced.
"""
import sqlite3
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from src.config import ZapierModulesConfig


class ZapierModuleStorage:
    def __init__(self, config: Optional[ZapierModulesConfig] = None):
        self.config = config or ZapierModulesConfig()
        self.sqlite_conn: Optional[sqlite3.Connection] = None
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialize SQLite database with WAL mode."""
        self.sqlite_conn = sqlite3.connect(self.config.sqlite_db_path, timeout=5.0)
        self.sqlite_conn.execute("PRAGMA journal_mode=WAL;")
        self.sqlite_conn.execute("PRAGMA busy_timeout=5000;")
        self.sqlite_conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id TEXT PRIMARY KEY,
                module_name TEXT NOT NULL,
                environment TEXT NOT NULL,
                duration_ms REAL NOT NULL,
                status TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        self.sqlite_conn.commit()

    def record_audit(self, log_id: str, module_name: str, environment: str, duration_ms: float, status: str, details: Dict[str, Any]) -> None:
        """Store audit record in local SQLite database."""
        if not self.sqlite_conn:
            return
        query = """
            INSERT OR REPLACE INTO audit_logs (log_id, module_name, environment, duration_ms, status, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        now = datetime.now(timezone.utc).isoformat()
        self.sqlite_conn.execute(query, (
            log_id,
            module_name,
            environment,
            duration_ms,
            status,
            json.dumps(details),
            now
        ))
        self.sqlite_conn.commit()

    def get_audit_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent audit records from SQLite."""
        if not self.sqlite_conn:
            return []
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT log_id, module_name, environment, duration_ms, status, details_json, created_at FROM audit_logs ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        return [
            {
                "log_id": r[0],
                "module_name": r[1],
                "environment": r[2],
                "duration_ms": r[3],
                "status": r[4],
                "details": json.loads(r[5]),
                "created_at": r[6],
            }
            for r in rows
        ]

    def init_postgres_schema(self) -> bool:
        """Initialize PostgreSQL 18 schema e10_zapier_modules if driver and database are available."""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.config.pg_host,
                port=self.config.pg_port,
                user=self.config.pg_user,
                password=self.config.pg_password,
                dbname=self.config.pg_database,
                connect_timeout=3
            )
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.config.pg_schema};")
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.execution_audits (
                        log_id VARCHAR(64) PRIMARY KEY,
                        module_name VARCHAR(64) NOT NULL,
                        environment VARCHAR(32) NOT NULL,
                        duration_ms NUMERIC(10, 2) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        details JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
            conn.commit()
            conn.close()
            return True
        except Exception:
            # Graceful offline mode when PostgreSQL cluster is not active
            return False

    def close(self) -> None:
        if self.sqlite_conn:
            self.sqlite_conn.close()
            self.sqlite_conn = None
