"""PostgreSQL 18 persistence and schema isolation manager for Chrome Data Exporter."""
import json
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import execute_batch
from src.config import ExtensionExporterConfig
from src.models import BatchExportJob, ExportRecord


class DatabaseManager:
    def __init__(self, config: ExtensionExporterConfig):
        self.config = config

    def get_connection(self):
        """Return native psycopg2 connection to PostgreSQL 18."""
        return psycopg2.connect(
            host=self.config.db_host,
            port=self.config.db_port,
            user=self.config.db_user,
            password=self.config.db_password,
            dbname=self.config.db_name
        )

    def init_postgres_schema(self) -> None:
        """Create schema and tables in PostgreSQL 18."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.config.db_schema};")
                cur.execute(f"""
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
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.db_schema}.scraped_records (
                        record_id VARCHAR(64) PRIMARY KEY,
                        job_id VARCHAR(64) NOT NULL,
                        source_url TEXT NOT NULL,
                        extracted_data JSONB NOT NULL,
                        captured_at TIMESTAMPTZ NOT NULL
                    );
                """)
            conn.commit()

    def record_job(self, job: BatchExportJob) -> bool:
        """Persist export job record into PostgreSQL."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.db_schema}.export_jobs (
                        job_id, rule_id, format, total_records, status, chunk_size, created_at, completed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (job_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        total_records = EXCLUDED.total_records,
                        completed_at = EXCLUDED.completed_at;
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

    def batch_insert_records(self, records: List[Dict[str, Any]], job_id: str, source_url: str = "https://example.com/data") -> int:
        """Stream batch of scraped records into PostgreSQL using execute_batch."""
        sql = f"""
            INSERT INTO {self.config.db_schema}.scraped_records (
                record_id, job_id, source_url, extracted_data, captured_at
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (record_id) DO UPDATE SET
                extracted_data = EXCLUDED.extracted_data;
        """
        data = [
            (
                rec.get("record_id", f"{job_id}_{idx}"),
                job_id,
                source_url,
                json.dumps(rec.get("extracted_data", rec)),
                rec.get("captured_at", "2026-10-14T00:00:00Z")
            )
            for idx, rec in enumerate(records)
        ]
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                execute_batch(cur, sql, data, page_size=1000)
            conn.commit()
        return len(data)

    def count_records(self, job_id: Optional[str] = None) -> int:
        """Count persisted records in PostgreSQL."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                if job_id:
                    cur.execute(f"SELECT COUNT(*) FROM {self.config.db_schema}.scraped_records WHERE job_id = %s;", (job_id,))
                else:
                    cur.execute(f"SELECT COUNT(*) FROM {self.config.db_schema}.scraped_records;")
                row = cur.fetchone()
                return row[0] if row else 0
