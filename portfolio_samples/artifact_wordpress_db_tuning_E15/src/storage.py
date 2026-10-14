"""Dual-tier storage: SQLite WAL local audit cache and PostgreSQL 18 on port 5433.
Strict zero em dash policy enforced.
"""
import sqlite3
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from src.config import WordPressOptimizerConfig
from src.models import DbHealthReport, QueryProfileRecord


class WordPressOptimizerStorage:
    def __init__(self, config: Optional[WordPressOptimizerConfig] = None):
        self.config = config or WordPressOptimizerConfig()
        self.sqlite_conn: Optional[sqlite3.Connection] = None
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialize SQLite database with WAL journal mode and busy timeout."""
        self.sqlite_conn = sqlite3.connect(self.config.sqlite_db_path, timeout=5.0)
        self.sqlite_conn.execute("PRAGMA journal_mode=WAL;")
        self.sqlite_conn.execute("PRAGMA busy_timeout=5000;")
        self.sqlite_conn.execute("""
            CREATE TABLE IF NOT EXISTS slow_query_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_sql TEXT NOT NULL,
                execution_time_ms REAL NOT NULL,
                rows_examined INTEGER NOT NULL,
                rows_sent INTEGER NOT NULL,
                severity TEXT NOT NULL,
                logged_at TEXT NOT NULL
            );
        """)
        self.sqlite_conn.execute("""
            CREATE TABLE IF NOT EXISTS db_health_audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_autoload_kb REAL NOT NULL,
                slow_queries_count INTEGER NOT NULL,
                missing_indexes_count INTEGER NOT NULL,
                orphaned_records_count INTEGER NOT NULL,
                health_score INTEGER NOT NULL,
                generated_at TEXT NOT NULL
            );
        """)
        self.sqlite_conn.commit()

    def record_slow_query(self, record: QueryProfileRecord) -> None:
        """Store slow query diagnostic record into local SQLite database."""
        if not self.sqlite_conn:
            return
        query = """
            INSERT INTO slow_query_logs (query_sql, execution_time_ms, rows_examined, rows_sent, severity, logged_at)
            VALUES (?, ?, ?, ?, ?, ?);
        """
        now = datetime.now(timezone.utc).isoformat()
        self.sqlite_conn.execute(query, (
            record.query_sql,
            record.execution_time_ms,
            record.rows_examined,
            record.rows_sent,
            record.bottleneck_severity.value,
            now
        ))
        self.sqlite_conn.commit()

    def record_health_report(self, report: DbHealthReport) -> None:
        """Store database health summary in SQLite."""
        if not self.sqlite_conn:
            return
        query = """
            INSERT INTO db_health_audits (total_autoload_kb, slow_queries_count, missing_indexes_count, orphaned_records_count, health_score, generated_at)
            VALUES (?, ?, ?, ?, ?, ?);
        """
        self.sqlite_conn.execute(query, (
            report.total_autoload_kb,
            report.slow_queries_count,
            report.missing_indexes_count,
            report.orphaned_records_count,
            report.health_score,
            report.generated_at
        ))
        self.sqlite_conn.commit()

    def get_slow_query_count(self) -> int:
        """Count total slow queries logged in SQLite."""
        if not self.sqlite_conn:
            return 0
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM slow_query_logs;")
        row = cursor.fetchone()
        return row[0] if row else 0

    def init_postgres_schema(self) -> bool:
        """Initialize PostgreSQL 18 schema e15_wp_db_opt on port 5433 if available."""
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
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.db_tuning_audits (
                        id SERIAL PRIMARY KEY,
                        autoload_kb REAL NOT NULL,
                        slow_query_count INT NOT NULL,
                        health_score INT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
