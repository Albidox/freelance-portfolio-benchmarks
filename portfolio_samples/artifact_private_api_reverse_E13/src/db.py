"""Dynamic PostgreSQL 18 schema loader (e13_private_api) on port 5433 with request logging.
Strict zero em dash policy enforced.
"""
import json
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from src.config import PrivateApiConfig


class DatabaseManager:
    """Manages PostgreSQL 18 connections, dynamic schema loading, and audit request logging."""

    def __init__(self, config: Optional[PrivateApiConfig] = None):
        self.config = config or PrivateApiConfig()
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
        """Create e13_private_api dynamic schema and associated logging tables."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.config.pg_schema};")
                
                # Request logs table
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.request_logs (
                        log_id BIGSERIAL PRIMARY KEY,
                        method VARCHAR(16) NOT NULL,
                        endpoint VARCHAR(255) NOT NULL,
                        status_code INT NOT NULL,
                        latency_ms DOUBLE PRECISION NOT NULL,
                        headers_json JSONB,
                        token_used VARCHAR(255),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)

                # Extracted records table
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.extracted_records (
                        entity_id VARCHAR(128) PRIMARY KEY,
                        entity_type VARCHAR(64) NOT NULL,
                        source_endpoint VARCHAR(255) NOT NULL,
                        payload JSONB NOT NULL,
                        extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
            return True
        except Exception as e:
            return False

    def log_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        latency_ms: float,
        headers: Optional[Dict[str, str]] = None,
        token_used: Optional[str] = None
    ) -> bool:
        """Insert outbound or intercepted API request log into PostgreSQL 18."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.pg_schema}.request_logs
                    (method, endpoint, status_code, latency_ms, headers_json, token_used)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (
                    method.upper(),
                    endpoint,
                    status_code,
                    latency_ms,
                    json.dumps(headers or {}),
                    token_used
                ))
            return True
        except Exception:
            return False

    def store_extracted_record(
        self,
        entity_id: str,
        entity_type: str,
        source_endpoint: str,
        payload: Dict[str, Any]
    ) -> bool:
        """Upsert an extracted record into PostgreSQL 18."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.pg_schema}.extracted_records
                    (entity_id, entity_type, source_endpoint, payload)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (entity_id) DO UPDATE
                    SET payload = EXCLUDED.payload,
                        extracted_at = NOW();
                """, (
                    entity_id,
                    entity_type,
                    source_endpoint,
                    json.dumps(payload)
                ))
            return True
        except Exception:
            return False

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent request logs."""
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT log_id, method, endpoint, status_code, latency_ms, token_used, created_at
                    FROM {self.config.pg_schema}.request_logs
                    ORDER BY log_id DESC
                    LIMIT %s;
                """, (limit,))
                return list(cur.fetchall())
        except Exception:
            return []

    def close(self) -> None:
        """Close active database connection."""
        if self._conn is not None and self._conn.closed == 0:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
