"""Dual-tier storage: SQLite WAL local audit cache + PostgreSQL 18 on port 5433.
Strict zero em dash policy enforced.
"""
import sqlite3
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from src.config import PrivateApiConfig
from src.models import ExtractedEntityRecord


class PrivateApiStorage:
    def __init__(self, config: Optional[PrivateApiConfig] = None):
        self.config = config or PrivateApiConfig()
        self.sqlite_conn: Optional[sqlite3.Connection] = None
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialize SQLite database with WAL journal mode and busy timeout."""
        self.sqlite_conn = sqlite3.connect(self.config.sqlite_db_path, timeout=5.0)
        self.sqlite_conn.execute("PRAGMA journal_mode=WAL;")
        self.sqlite_conn.execute("PRAGMA busy_timeout=5000;")
        self.sqlite_conn.execute("""
            CREATE TABLE IF NOT EXISTS extracted_entities (
                entity_id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                source_endpoint TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                extracted_at TEXT NOT NULL
            );
        """)
        self.sqlite_conn.commit()

    def store_entity(self, record: ExtractedEntityRecord) -> None:
        """Persist extracted entity record into local SQLite database."""
        if not self.sqlite_conn:
            return
        query = """
            INSERT OR REPLACE INTO extracted_entities (entity_id, entity_type, source_endpoint, payload_json, extracted_at)
            VALUES (?, ?, ?, ?, ?);
        """
        self.sqlite_conn.execute(query, (
            record.entity_id,
            record.entity_type,
            record.source_endpoint,
            json.dumps(record.payload),
            record.extracted_at
        ))
        self.sqlite_conn.commit()

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve single entity by ID from SQLite."""
        if not self.sqlite_conn:
            return None
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT entity_id, entity_type, source_endpoint, payload_json, extracted_at FROM extracted_entities WHERE entity_id = ?", (entity_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "entity_id": row[0],
            "entity_type": row[1],
            "source_endpoint": row[2],
            "payload": json.loads(row[3]),
            "extracted_at": row[4]
        }

    def init_postgres_schema(self) -> bool:
        """Initialize PostgreSQL 18 schema e13_private_api on port 5433 if available."""
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
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.extracted_records (
                        entity_id VARCHAR(128) PRIMARY KEY,
                        entity_type VARCHAR(64) NOT NULL,
                        source_endpoint VARCHAR(255) NOT NULL,
                        payload JSONB NOT NULL,
                        extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def close(self) -> None:
        if self.sqlite_conn:
            self.sqlite_conn.close()
            self.sqlite_conn = None
