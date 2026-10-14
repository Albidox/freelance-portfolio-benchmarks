"""Dynamic PostgreSQL 18 schema loader and execution audit logger.
Dynamic schema isolation e11_micropython_iot on port 5433.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional
import json
from datetime import datetime, timezone
from src.config import IoTFirmwareConfig


class DatabaseManager:
    """Manages PostgreSQL 18 schema initialization and batch telemetry persistence."""

    def __init__(self, config: Optional[IoTFirmwareConfig] = None):
        self.config = config or IoTFirmwareConfig()
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
                connect_timeout=3,
            )
            self._connected = True
            return self.conn
        except Exception:
            self._connected = False
            return None

    def init_schema(self) -> bool:
        """Create schema e11_micropython_iot and required tables if not existing."""
        conn = self.get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.config.pg_schema};")
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.execution_audits (
                        log_id VARCHAR(64) PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        event_type VARCHAR(64) NOT NULL,
                        duration_ms NUMERIC(10, 2) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        details JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.telemetry_records (
                        sample_id VARCHAR(64) PRIMARY KEY,
                        device_id VARCHAR(64) NOT NULL,
                        temperature_c NUMERIC(6, 2) NOT NULL,
                        humidity_pct NUMERIC(5, 2) NOT NULL,
                        battery_mv INTEGER NOT NULL,
                        sequence_num INTEGER NOT NULL,
                        details JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.sensor_events (
                        event_id VARCHAR(64) PRIMARY KEY,
                        sensor_id VARCHAR(64) NOT NULL,
                        event_type VARCHAR(32) NOT NULL,
                        value NUMERIC(10, 4) NOT NULL,
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
        device_id: str,
        event_type: str,
        duration_ms: float,
        status: str,
        details: Dict[str, Any],
    ) -> bool:
        """Persist single execution audit record."""
        conn = self.get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.pg_schema}.execution_audits
                    (log_id, device_id, event_type, duration_ms, status, details, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (log_id) DO UPDATE SET
                        duration_ms = EXCLUDED.duration_ms,
                        status = EXCLUDED.status,
                        details = EXCLUDED.details;
                """, (
                    log_id,
                    device_id,
                    event_type,
                    duration_ms,
                    status,
                    json.dumps(details),
                    datetime.now(timezone.utc),
                ))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    def insert_telemetry(
        self,
        sample_id: str,
        device_id: str,
        temp_c: float,
        hum_pct: float,
        batt_mv: int,
        seq: int,
        details: Dict[str, Any],
    ) -> bool:
        """Persist single telemetry record to PostgreSQL 18."""
        conn = self.get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.pg_schema}.telemetry_records
                    (sample_id, device_id, temperature_c, humidity_pct, battery_mv, sequence_num, details, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (sample_id) DO UPDATE SET
                        temperature_c = EXCLUDED.temperature_c,
                        humidity_pct = EXCLUDED.humidity_pct,
                        battery_mv = EXCLUDED.battery_mv,
                        details = EXCLUDED.details;
                """, (
                    sample_id,
                    device_id,
                    temp_c,
                    hum_pct,
                    batt_mv,
                    seq,
                    json.dumps(details),
                    datetime.now(timezone.utc),
                ))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    def insert_telemetry_batch(self, records: List[Dict[str, Any]]) -> int:
        """Batch insert telemetry records."""
        conn = self.get_connection()
        if not conn or not records:
            return 0
        try:
            count = 0
            with conn.cursor() as cur:
                for r in records:
                    cur.execute(f"""
                        INSERT INTO {self.config.pg_schema}.telemetry_records
                        (sample_id, device_id, temperature_c, humidity_pct, battery_mv, sequence_num, details, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (sample_id) DO NOTHING;
                    """, (
                        r["sample_id"],
                        r["device_id"],
                        r["temperature_c"],
                        r["humidity_pct"],
                        r["battery_mv"],
                        r["sequence_num"],
                        json.dumps(r.get("details", {})),
                        datetime.now(timezone.utc),
                    ))
                    count += 1
            conn.commit()
            return count
        except Exception:
            conn.rollback()
            return 0

    def insert_sensor_event(
        self,
        event_id: str,
        sensor_id: str,
        event_type: str,
        value: float,
        status: str,
    ) -> bool:
        """Persist sensor event record."""
        conn = self.get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.pg_schema}.sensor_events
                    (event_id, sensor_id, event_type, value, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id) DO NOTHING;
                """, (
                    event_id,
                    sensor_id,
                    event_type,
                    value,
                    status,
                    datetime.now(timezone.utc),
                ))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    def get_audit_count(self) -> int:
        """Count total audit logs."""
        conn = self.get_connection()
        if not conn:
            return 0
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self.config.pg_schema}.execution_audits;")
                row = cur.fetchone()
                return int(row[0]) if row else 0
        except Exception:
            return 0

    def get_telemetry_count(self) -> int:
        """Count total telemetry records."""
        conn = self.get_connection()
        if not conn:
            return 0
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self.config.pg_schema}.telemetry_records;")
                row = cur.fetchone()
                return int(row[0]) if row else 0
        except Exception:
            return 0

    def close(self) -> None:
        """Close database connection."""
        if self.conn and not self.conn.closed:
            self.conn.close()
            self.conn = None
            self._connected = False
