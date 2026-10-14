"""Dynamic PostgreSQL 18 connection pool manager with schema loader for e18_sheets_airtable_sync.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional
import json
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from src.config import SheetsAirtableSyncConfig
from src.models import SyncCycleReport, SyncRecordItem, ConflictResolutionResult


class DatabaseManager:
    """Manages PostgreSQL 18 connection pool, dynamic schema setup, and sync audit logging."""

    def __init__(self, config: Optional[SheetsAirtableSyncConfig] = None):
        self.config = config or SheetsAirtableSyncConfig()
        self._pool: Optional[pool.SimpleConnectionPool] = None
        self._init_pool()

    def _init_pool(self) -> None:
        """Initializes connection pool for PostgreSQL 18 on port 5433."""
        try:
            self._pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=self.config.pg_host,
                port=self.config.pg_port,
                user=self.config.pg_user,
                password=self.config.pg_password,
                dbname=self.config.pg_database,
                connect_timeout=5
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
        """Creates target schema e18_sheets_airtable_sync and audit tables in PostgreSQL 18."""
        conn = None
        try:
            conn = self.get_connection()
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.config.target_schema};")
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.target_schema}.sync_audit_log (
                        id BIGSERIAL PRIMARY KEY,
                        cycle_id VARCHAR(64) UNIQUE NOT NULL,
                        direction VARCHAR(32) NOT NULL,
                        records_scanned INTEGER NOT NULL,
                        records_added INTEGER NOT NULL,
                        records_updated INTEGER NOT NULL,
                        records_deleted INTEGER NOT NULL,
                        conflicts_resolved INTEGER NOT NULL,
                        conflicts_quarantined INTEGER NOT NULL,
                        elapsed_seconds REAL NOT NULL,
                        completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.target_schema}.sync_record_snapshots (
                        id BIGSERIAL PRIMARY KEY,
                        entity_id VARCHAR(128) NOT NULL,
                        source VARCHAR(32) NOT NULL,
                        fingerprint VARCHAR(64) NOT NULL,
                        fields JSONB NOT NULL,
                        formula_fields JSONB,
                        last_modified TIMESTAMPTZ,
                        synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        CONSTRAINT uq_entity_source UNIQUE (entity_id, source)
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.target_schema}.sync_conflict_events (
                        id BIGSERIAL PRIMARY KEY,
                        entity_id VARCHAR(128) NOT NULL,
                        strategy_applied VARCHAR(64) NOT NULL,
                        winning_source VARCHAR(32) NOT NULL,
                        quarantined BOOLEAN NOT NULL DEFAULT FALSE,
                        quarantine_reason TEXT,
                        resolved_fields JSONB,
                        resolved_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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

    def log_sync_cycle(self, report: SyncCycleReport) -> bool:
        """Logs a sync cycle report to PostgreSQL 18."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.target_schema}.sync_audit_log (
                        cycle_id, direction, records_scanned, records_added,
                        records_updated, records_deleted, conflicts_resolved,
                        conflicts_quarantined, elapsed_seconds
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (cycle_id) DO UPDATE SET
                        records_scanned = EXCLUDED.records_scanned,
                        records_added = EXCLUDED.records_added,
                        records_updated = EXCLUDED.records_updated,
                        records_deleted = EXCLUDED.records_deleted,
                        conflicts_resolved = EXCLUDED.conflicts_resolved,
                        conflicts_quarantined = EXCLUDED.conflicts_quarantined,
                        elapsed_seconds = EXCLUDED.elapsed_seconds;
                """, (
                    report.cycle_id,
                    report.direction.value if hasattr(report.direction, "value") else str(report.direction),
                    report.records_scanned,
                    report.records_added,
                    report.records_updated,
                    report.records_deleted,
                    report.conflicts_resolved,
                    report.conflicts_quarantined,
                    report.elapsed_seconds
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

    def log_conflict_event(self, conflict_res: ConflictResolutionResult) -> bool:
        """Logs a conflict resolution event to PostgreSQL 18."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.target_schema}.sync_conflict_events (
                        entity_id, strategy_applied, winning_source,
                        quarantined, quarantine_reason, resolved_fields
                    ) VALUES (%s, %s, %s, %s, %s, %s);
                """, (
                    conflict_res.entity_id,
                    conflict_res.strategy_applied.value if hasattr(conflict_res.strategy_applied, "value") else str(conflict_res.strategy_applied),
                    conflict_res.winning_source,
                    conflict_res.quarantined,
                    conflict_res.quarantine_reason,
                    json.dumps(conflict_res.resolved_fields)
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

    def upsert_record_snapshot(self, record: SyncRecordItem, source: str) -> bool:
        """Stores or updates record snapshot in PostgreSQL 18."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.target_schema}.sync_record_snapshots (
                        entity_id, source, fingerprint, fields, formula_fields, last_modified
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (entity_id, source) DO UPDATE SET
                        fingerprint = EXCLUDED.fingerprint,
                        fields = EXCLUDED.fields,
                        formula_fields = EXCLUDED.formula_fields,
                        last_modified = EXCLUDED.last_modified,
                        synced_at = NOW();
                """, (
                    record.entity_id,
                    source,
                    record.fingerprint or record.calculate_fingerprint(),
                    json.dumps(record.fields),
                    json.dumps(record.formula_fields) if record.formula_fields else None,
                    record.last_modified
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

    def get_cycle(self, cycle_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves sync cycle record from PostgreSQL 18."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SELECT * FROM {self.config.target_schema}.sync_audit_log WHERE cycle_id = %s;", (cycle_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception:
            return None
        finally:
            if conn is not None:
                self.release_connection(conn)
