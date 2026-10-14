"""Dynamic PostgreSQL 18 connection pool manager with transaction isolation.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from src.config import DatabaseMigrationConfig
from src.models import MigrationAuditLog, ChunkProgress, ConsistencyReport


class DatabaseManager:
    """Manages PostgreSQL 18 connection pool, transaction isolation, and schema operations."""

    def __init__(self, config: Optional[DatabaseMigrationConfig] = None):
        self.config = config or DatabaseMigrationConfig()
        self._pool: Optional[pool.SimpleConnectionPool] = None
        self._init_pool()

    def _init_pool(self) -> None:
        """Initializes connection pool for PostgreSQL 18."""
        try:
            self._pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=self.config.max_workers + 2,
                host=self.config.pg_host,
                port=self.config.pg_port,
                user=self.config.pg_user,
                password=self.config.pg_password,
                dbname=self.config.pg_database,
                connect_timeout=int(self.config.connection_timeout_seconds)
            )
        except Exception:
            self._pool = None

    def get_connection(self):
        """Retrieves a connection from the pool or creates a standalone connection."""
        if self._pool is not None:
            try:
                return self._pool.getconn()
            except Exception:
                pass
        return psycopg2.connect(**self.config.get_pg_connection_dict())

    def release_connection(self, conn) -> None:
        """Returns connection back to pool."""
        if self._pool is not None and conn is not None:
            try:
                self._pool.putconn(conn)
                return
            except Exception:
                pass
        if conn is not None and not conn.closed:
            conn.close()

    def close_all(self) -> None:
        """Closes all pooled connections."""
        if self._pool is not None:
            try:
                self._pool.closeall()
            except Exception:
                pass
            self._pool = None

    def init_schema(self) -> bool:
        """Creates target schema e16_db_migration and audit tables in PostgreSQL 18."""
        conn = None
        try:
            conn = self.get_connection()
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.config.target_schema};")
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.target_schema}.migration_runs (
                        id BIGSERIAL PRIMARY KEY,
                        run_id VARCHAR(64) UNIQUE NOT NULL,
                        source_type VARCHAR(32) NOT NULL,
                        target_schema VARCHAR(64) NOT NULL,
                        table_name VARCHAR(128) NOT NULL,
                        total_migrated INT NOT NULL,
                        quarantined_count INT NOT NULL,
                        elapsed_seconds REAL NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.target_schema}.chunk_checkpoints (
                        id BIGSERIAL PRIMARY KEY,
                        table_name VARCHAR(128) NOT NULL,
                        chunk_id INT NOT NULL,
                        start_offset INT NOT NULL,
                        end_offset INT NOT NULL,
                        records_processed INT NOT NULL,
                        recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.target_schema}.reconciliation_audits (
                        id BIGSERIAL PRIMARY KEY,
                        table_name VARCHAR(128) NOT NULL,
                        source_count INT NOT NULL,
                        target_count INT NOT NULL,
                        source_root_sha256 VARCHAR(64) NOT NULL,
                        target_root_sha256 VARCHAR(64) NOT NULL,
                        is_verified BOOLEAN NOT NULL,
                        mismatches INT NOT NULL,
                        verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
            conn.commit()
            return True
        except Exception:
            if conn is not None:
                conn.rollback()
            return False
        finally:
            if conn is not None:
                self.release_connection(conn)

    def log_migration_run(self, audit: MigrationAuditLog) -> bool:
        """Records audit log to PostgreSQL 18 under transaction isolation."""
        conn = None
        try:
            conn = self.get_connection()
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.target_schema}.migration_runs
                    (run_id, source_type, target_schema, table_name, total_migrated, quarantined_count, elapsed_seconds, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_id) DO UPDATE SET
                        total_migrated = EXCLUDED.total_migrated,
                        quarantined_count = EXCLUDED.quarantined_count,
                        elapsed_seconds = EXCLUDED.elapsed_seconds,
                        status = EXCLUDED.status;
                """, (
                    audit.run_id, audit.source_type, audit.target_schema, audit.table_name,
                    audit.total_migrated, audit.quarantined_count, audit.elapsed_seconds, audit.status.value
                ))
            conn.commit()
            return True
        except Exception:
            if conn is not None:
                conn.rollback()
            return False
        finally:
            if conn is not None:
                self.release_connection(conn)

    def log_chunk_progress(self, progress: ChunkProgress) -> bool:
        """Records chunk checkpoint to PostgreSQL 18."""
        conn = None
        try:
            conn = self.get_connection()
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.target_schema}.chunk_checkpoints
                    (table_name, chunk_id, start_offset, end_offset, records_processed)
                    VALUES (%s, %s, %s, %s, %s);
                """, (
                    progress.table_name, progress.chunk_id, progress.start_offset,
                    progress.end_offset, progress.processed_records
                ))
            conn.commit()
            return True
        except Exception:
            if conn is not None:
                conn.rollback()
            return False
        finally:
            if conn is not None:
                self.release_connection(conn)
