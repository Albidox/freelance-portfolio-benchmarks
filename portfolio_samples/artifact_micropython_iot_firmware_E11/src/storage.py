"""Dual-tier storage: SQLite WAL local telemetry database + PostgreSQL 18 on port 5433.
Strict zero em dash policy enforced.
"""
import sqlite3
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from src.config import IoTFirmwareConfig


class IoTTelemetryStorage:
    """Dual-tier persistence engine buffering locally in SQLite WAL and syncing to PostgreSQL 18."""

    def __init__(self, config: Optional[IoTFirmwareConfig] = None):
        self.config = config or IoTFirmwareConfig()
        self.sqlite_conn: Optional[sqlite3.Connection] = None
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialize SQLite database with WAL journal mode and busy timeout."""
        self.sqlite_conn = sqlite3.connect(self.config.sqlite_db_path, timeout=5.0)
        self.sqlite_conn.execute("PRAGMA journal_mode=WAL;")
        self.sqlite_conn.execute("PRAGMA busy_timeout=5000;")
        self.sqlite_conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_logs (
                sample_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                temperature_c REAL NOT NULL,
                humidity_pct REAL NOT NULL,
                battery_mv INTEGER NOT NULL,
                sequence_num INTEGER NOT NULL,
                details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        self.sqlite_conn.commit()

    def record_telemetry(
        self,
        sample_id: str,
        device_id: str,
        temp_c: float,
        hum_pct: float,
        batt_mv: int,
        seq: int,
        details: Dict[str, Any]
    ) -> None:
        """Persist telemetry record to local SQLite WAL database."""
        if not self.sqlite_conn:
            return
        query = """
            INSERT OR REPLACE INTO telemetry_logs
            (sample_id, device_id, temperature_c, humidity_pct, battery_mv, sequence_num, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        now = datetime.now(timezone.utc).isoformat()
        self.sqlite_conn.execute(query, (
            sample_id,
            device_id,
            temp_c,
            hum_pct,
            batt_mv,
            seq,
            json.dumps(details),
            now
        ))
        self.sqlite_conn.commit()

    def get_recent_telemetry(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent telemetry records from SQLite."""
        if not self.sqlite_conn:
            return []
        cursor = self.sqlite_conn.cursor()
        cursor.execute(
            "SELECT sample_id, device_id, temperature_c, humidity_pct, battery_mv, sequence_num, details_json, created_at "
            "FROM telemetry_logs ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        return [
            {
                "sample_id": r[0],
                "device_id": r[1],
                "temperature_c": r[2],
                "humidity_pct": r[3],
                "battery_mv": r[4],
                "sequence_num": r[5],
                "details": json.loads(r[6]),
                "created_at": r[7],
            }
            for r in rows
        ]

    def init_postgres_schema(self) -> bool:
        """Initialize PostgreSQL 18 schema e11_micropython_iot if available."""
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
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.iot_telemetry_records (
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
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Close database connections."""
        if self.sqlite_conn:
            self.sqlite_conn.close()
            self.sqlite_conn = None
