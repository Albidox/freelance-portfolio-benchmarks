"""Dynamic PostgreSQL 18 schema loader and execution audit logger.
Dynamic schema isolation e10_zapier_modules on port 5433.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional
import json
from datetime import datetime, timezone
from src.config import ZapierModulesConfig


class DatabaseManager:
    """Manages PostgreSQL 18 schema initialization and batch telemetry persistence."""

    def __init__(self, config: Optional[ZapierModulesConfig] = None):
        self.config = config or ZapierModulesConfig()
        self.conn = None
        self._connected = False

    def get_connection(self):
        """Establish or return active PostgreSQL connection."""
        if self.conn is not None and not self.conn.closed:
            return self.conn
        try:
            import psycopg2
            self.conn = psycopg2.connect(
                host=self.config.pg_host,
                port=self.config.pg_port,
                user=self.config.pg_user,
                password=self.config.pg_password,
                dbname=self.config.pg_database,
                connect_timeout=3
            )
            self._connected = True
            return self.conn
        except Exception:
            self._connected = False
            return None

    def init_schema(self) -> bool:
        """Create schema e10_zapier_modules and required audit tables if not existing."""
        conn = self.get_connection()
        if not conn:
            return False
        try:
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
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.transformation_records (
                        record_id VARCHAR(64) PRIMARY KEY,
                        batch_id VARCHAR(64) NOT NULL,
                        source_format VARCHAR(32) NOT NULL,
                        target_format VARCHAR(32) NOT NULL,
                        payload_size_bytes INT NOT NULL,
                        duration_ms NUMERIC(10, 2) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    def insert_audit(
        self,
        log_id: str,
        module_name: str,
        environment: str,
        duration_ms: float,
        status: str,
        details: Dict[str, Any]
    ) -> bool:
        """Persist single execution audit record."""
        conn = self.get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.pg_schema}.execution_audits
                    (log_id, module_name, environment, duration_ms, status, details, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (log_id) DO UPDATE SET
                        duration_ms = EXCLUDED.duration_ms,
                        status = EXCLUDED.status,
                        details = EXCLUDED.details;
                """, (
                    log_id,
                    module_name,
                    environment,
                    duration_ms,
                    status,
                    json.dumps(details),
                    datetime.now(timezone.utc)
                ))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    def batch_insert_audits(self, records: List[Dict[str, Any]]) -> int:
        """Batch insert audit records using parameterized execute_batch."""
        conn = self.get_connection()
        if not conn or not records:
            return 0
        try:
            from psycopg2.extras import execute_batch
            query = f"""
                INSERT INTO {self.config.pg_schema}.execution_audits
                (log_id, module_name, environment, duration_ms, status, details, created_at)
                VALUES (%(log_id)s, %(module_name)s, %(environment)s, %(duration_ms)s, %(status)s, %(details)s, %(created_at)s)
                ON CONFLICT (log_id) DO UPDATE SET
                    duration_ms = EXCLUDED.duration_ms,
                    status = EXCLUDED.status,
                    details = EXCLUDED.details;
            """
            params = []
            now = datetime.now(timezone.utc)
            for r in records:
                params.append({
                    "log_id": r["log_id"],
                    "module_name": r["module_name"],
                    "environment": r.get("environment", "ZAPIER"),
                    "duration_ms": r["duration_ms"],
                    "status": r.get("status", "SUCCESS"),
                    "details": json.dumps(r.get("details", {})),
                    "created_at": r.get("created_at", now)
                })
            with conn.cursor() as cur:
                execute_batch(cur, query, params, page_size=200)
            conn.commit()
            return len(records)
        except Exception:
            conn.rollback()
            return 0

    def insert_transformation_record(
        self,
        record_id: str,
        batch_id: str,
        source_format: str,
        target_format: str,
        payload_size_bytes: int,
        duration_ms: float,
        status: str = "SUCCESS"
    ) -> bool:
        """Persist structured transformation metric record."""
        conn = self.get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.pg_schema}.transformation_records
                    (record_id, batch_id, source_format, target_format, payload_size_bytes, duration_ms, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (record_id) DO NOTHING;
                """, (
                    record_id,
                    batch_id,
                    source_format,
                    target_format,
                    payload_size_bytes,
                    duration_ms,
                    status,
                    datetime.now(timezone.utc)
                ))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    def get_audit_summary(self) -> Dict[str, Any]:
        """Fetch audit metrics and summary counts."""
        conn = self.get_connection()
        if not conn:
            return {"connected": False, "total_records": 0}
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*), AVG(duration_ms) FROM {self.config.pg_schema}.execution_audits;")
                row = cur.fetchone()
                count = row[0] if row else 0
                avg_dur = row[1] if row else 0.0
                return {
                    "connected": True,
                    "total_records": count or 0,
                    "avg_duration_ms": round(float(avg_dur or 0.0), 2)
                }
        except Exception:
            return {"connected": False, "total_records": 0}

    def close(self) -> None:
        """Close database connection cleanly."""
        if self.conn and not self.conn.closed:
            self.conn.close()
            self.conn = None
            self._connected = False
