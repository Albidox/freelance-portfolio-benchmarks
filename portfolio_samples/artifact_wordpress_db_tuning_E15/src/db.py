"""Dynamic PostgreSQL 18 schema loader (e15_wp_db_opt) on port 5433 with execution logging.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from src.config import WordPressOptimizerConfig
from src.models import QueryProfileRecord, IndexRecommendation, DbHealthReport


class DatabaseManager:
    """Manages PostgreSQL 18 connections, dynamic schema loading, and execution logging."""

    def __init__(self, config: Optional[WordPressOptimizerConfig] = None):
        self.config = config or WordPressOptimizerConfig()
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
        """Create e15_wp_db_opt schema and audit tables."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.config.pg_schema};")
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.slow_query_audits (
                        id BIGSERIAL PRIMARY KEY,
                        query_sql TEXT NOT NULL,
                        execution_time_ms REAL NOT NULL,
                        rows_examined INT NOT NULL,
                        rows_sent INT NOT NULL,
                        severity VARCHAR(32) NOT NULL,
                        logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.autoload_audits (
                        id BIGSERIAL PRIMARY KEY,
                        total_autoload_kb REAL NOT NULL,
                        bloated_options_count INT NOT NULL,
                        migrations_count INT NOT NULL,
                        audited_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.index_recommendations (
                        id BIGSERIAL PRIMARY KEY,
                        table_name VARCHAR(64) NOT NULL,
                        index_name VARCHAR(64) NOT NULL,
                        columns_csv TEXT NOT NULL,
                        estimated_speedup_pct REAL NOT NULL,
                        ddl_statement TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.tuning_benchmarks (
                        id BIGSERIAL PRIMARY KEY,
                        benchmark_name VARCHAR(128) NOT NULL,
                        pre_ms REAL NOT NULL,
                        post_ms REAL NOT NULL,
                        speedup_x REAL NOT NULL,
                        latency_reduction_pct REAL NOT NULL,
                        executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
            return True
        except Exception:
            return False

    def log_slow_query(
        self,
        query_sql: str,
        execution_time_ms: float,
        rows_examined: int,
        rows_sent: int,
        severity: str
    ) -> bool:
        """Insert slow query execution record into PostgreSQL 18."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.pg_schema}.slow_query_audits
                    (query_sql, execution_time_ms, rows_examined, rows_sent, severity)
                    VALUES (%s, %s, %s, %s, %s);
                """, (query_sql, execution_time_ms, rows_examined, rows_sent, severity))
            return True
        except Exception:
            return False

    def log_autoload_audit(
        self,
        total_autoload_kb: float,
        bloated_options_count: int,
        migrations_count: int
    ) -> bool:
        """Insert autoload analysis audit log into PostgreSQL 18."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.pg_schema}.autoload_audits
                    (total_autoload_kb, bloated_options_count, migrations_count)
                    VALUES (%s, %s, %s);
                """, (total_autoload_kb, bloated_options_count, migrations_count))
            return True
        except Exception:
            return False

    def log_index_recommendation(self, rec: IndexRecommendation) -> bool:
        """Insert index recommendation record into PostgreSQL 18."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.pg_schema}.index_recommendations
                    (table_name, index_name, columns_csv, estimated_speedup_pct, ddl_statement)
                    VALUES (%s, %s, %s, %s, %s);
                """, (
                    rec.table_name,
                    rec.index_name,
                    ", ".join(rec.target_columns),
                    rec.estimated_speedup_pct,
                    rec.ddl_statement
                ))
            return True
        except Exception:
            return False

    def log_benchmark(
        self,
        benchmark_name: str,
        pre_ms: float,
        post_ms: float,
        speedup_x: float,
        latency_reduction_pct: float
    ) -> bool:
        """Insert query latency benchmark comparison into PostgreSQL 18."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.pg_schema}.tuning_benchmarks
                    (benchmark_name, pre_ms, post_ms, speedup_x, latency_reduction_pct)
                    VALUES (%s, %s, %s, %s, %s);
                """, (benchmark_name, pre_ms, post_ms, speedup_x, latency_reduction_pct))
            return True
        except Exception:
            return False

    def batch_log_slow_queries(self, records: List[QueryProfileRecord]) -> int:
        """Batch insert query profile records into PostgreSQL 18."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                args = [
                    (r.query_sql, r.execution_time_ms, r.rows_examined, r.rows_sent, r.bottleneck_severity.value)
                    for r in records
                ]
                cur.executemany(f"""
                    INSERT INTO {self.config.pg_schema}.slow_query_audits
                    (query_sql, execution_time_ms, rows_examined, rows_sent, severity)
                    VALUES (%s, %s, %s, %s, %s);
                """, args)
            return len(records)
        except Exception:
            return 0

    def close(self) -> None:
        """Close database connection."""
        if self._conn and self._conn.closed == 0:
            self._conn.close()
            self._conn = None
