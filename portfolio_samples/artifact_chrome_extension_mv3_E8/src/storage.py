"""Storage persistence engine targeting Native PostgreSQL 18 and SQLite WAL."""
import sqlite3
import json
from typing import Dict, Any, List, Optional
from src.config import ExtensionExporterConfig
from src.models import BatchExportJob


class ExtensionStorage:
    def __init__(self, config: ExtensionExporterConfig):
        self.config = config

    def init_sqlite_cache(self) -> None:
        """Initialize local SQLite WAL database for caching browser exports."""
        with sqlite3.connect(self.config.sqlite_cache_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS export_jobs (
                    job_id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL,
                    format TEXT NOT NULL,
                    total_records INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    chunk_size INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scraped_records (
                    record_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    extracted_json TEXT NOT NULL,
                    captured_at TEXT NOT NULL
                );
            """)
            conn.commit()

    def record_job_sqlite(self, job: BatchExportJob) -> bool:
        """Persist export job record into SQLite cache."""
        with sqlite3.connect(self.config.sqlite_cache_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO export_jobs (
                    job_id, rule_id, format, total_records, status, chunk_size, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                job.job_id,
                job.rule_id,
                job.format.value,
                job.total_records,
                job.status.value,
                job.chunk_size,
                job.created_at,
                job.completed_at
            ))
            conn.commit()
        return True

    def record_scraped_records_sqlite(self, records: List[Dict[str, Any]], job_id: str) -> int:
        """Persist raw scraped records into SQLite cache in batch."""
        with sqlite3.connect(self.config.sqlite_cache_path) as conn:
            rows = [
                (
                    rec.get("record_id", f"{job_id}_{idx}"),
                    job_id,
                    json.dumps(rec.get("extracted_data", rec)),
                    rec.get("captured_at", "")
                )
                for idx, rec in enumerate(records)
            ]
            conn.executemany("""
                INSERT OR REPLACE INTO scraped_records (record_id, job_id, extracted_json, captured_at)
                VALUES (?, ?, ?, ?);
            """, rows)
            conn.commit()
            return len(rows)

    def get_postgres_schema_ddl(self) -> str:
        """Return PostgreSQL 18 DDL for dynamic schema isolation."""
        return f"""
        CREATE SCHEMA IF NOT EXISTS {self.config.db_schema};
        CREATE TABLE IF NOT EXISTS {self.config.db_schema}.export_jobs (
            job_id VARCHAR(64) PRIMARY KEY,
            rule_id VARCHAR(64) NOT NULL,
            format VARCHAR(16) NOT NULL,
            total_records INTEGER NOT NULL,
            status VARCHAR(32) NOT NULL,
            chunk_size INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ
        );
        CREATE TABLE IF NOT EXISTS {self.config.db_schema}.scraped_records (
            record_id VARCHAR(64) PRIMARY KEY,
            job_id VARCHAR(64) NOT NULL,
            source_url TEXT NOT NULL,
            extracted_data JSONB NOT NULL,
            captured_at TIMESTAMPTZ NOT NULL
        );
        """
