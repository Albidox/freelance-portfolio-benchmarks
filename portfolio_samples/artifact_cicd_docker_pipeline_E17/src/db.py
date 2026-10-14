"""Dynamic PostgreSQL 18 connection pool manager with schema loader for e17_cicd_pipeline.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from src.config import DeploymentPipelineConfig
from src.models import DeploymentRecord, HealthProbeEvent, DeploymentAuditLog


class DatabaseManager:
    """Manages PostgreSQL 18 connection pool, dynamic schema setup, and deployment audit logging."""

    def __init__(self, config: Optional[DeploymentPipelineConfig] = None):
        self.config = config or DeploymentPipelineConfig()
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
                connect_timeout=int(self.config.health_check_timeout_seconds)
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
        """Creates target schema e17_cicd_pipeline and audit tables in PostgreSQL 18."""
        conn = None
        try:
            conn = self.get_connection()
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.config.target_schema};")
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.target_schema}.deployments (
                        id BIGSERIAL PRIMARY KEY,
                        deployment_id VARCHAR(64) UNIQUE NOT NULL,
                        strategy VARCHAR(32) NOT NULL,
                        image_tag VARCHAR(255) NOT NULL,
                        active_container_id VARCHAR(64) NOT NULL,
                        previous_container_id VARCHAR(64),
                        status VARCHAR(32) NOT NULL,
                        health_check_status VARCHAR(32) NOT NULL,
                        rollback_triggered BOOLEAN NOT NULL DEFAULT FALSE,
                        elapsed_seconds REAL NOT NULL,
                        deployed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.target_schema}.container_health_probes (
                        id BIGSERIAL PRIMARY KEY,
                        probe_id VARCHAR(64) NOT NULL,
                        container_id VARCHAR(64) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        latency_ms REAL NOT NULL,
                        probe_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.target_schema}.deployment_audit_events (
                        id BIGSERIAL PRIMARY KEY,
                        run_id VARCHAR(64) NOT NULL,
                        deployment_id VARCHAR(64) NOT NULL,
                        event_type VARCHAR(64) NOT NULL,
                        details TEXT,
                        recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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

    def log_deployment(self, record: DeploymentRecord) -> bool:
        """Logs a deployment record to PostgreSQL 18."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.target_schema}.deployments (
                        deployment_id, strategy, image_tag, active_container_id,
                        previous_container_id, status, health_check_status,
                        rollback_triggered, elapsed_seconds
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (deployment_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        health_check_status = EXCLUDED.health_check_status,
                        rollback_triggered = EXCLUDED.rollback_triggered,
                        elapsed_seconds = EXCLUDED.elapsed_seconds;
                """, (
                    record.deployment_id,
                    record.strategy.value if hasattr(record.strategy, "value") else str(record.strategy),
                    record.image_tag,
                    record.active_container_id,
                    record.previous_container_id,
                    record.status.value if hasattr(record.status, "value") else str(record.status),
                    record.health_check_status.value if hasattr(record.health_check_status, "value") else str(record.health_check_status),
                    record.rollback_triggered,
                    record.elapsed_seconds
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

    def log_health_probe(self, probe: HealthProbeEvent) -> bool:
        """Logs a container health probe event."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.target_schema}.container_health_probes (
                        probe_id, container_id, status, latency_ms
                    ) VALUES (%s, %s, %s, %s);
                """, (
                    probe.probe_id,
                    probe.container_id,
                    probe.status.value if hasattr(probe.status, "value") else str(probe.status),
                    probe.latency_ms
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

    def log_audit_event(self, run_id: str, deployment_id: str, event_type: str, details: str) -> bool:
        """Records an audit event into deployment_audit_events table."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.target_schema}.deployment_audit_events (
                        run_id, deployment_id, event_type, details
                    ) VALUES (%s, %s, %s, %s);
                """, (run_id, deployment_id, event_type, details))
                conn.commit()
                return True
        except Exception:
            if conn is not None:
                conn.rollback()
            return False
        finally:
            if conn is not None:
                self.release_connection(conn)

    def get_deployment_count(self) -> int:
        """Returns total deployment records in PostgreSQL 18."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self.config.target_schema}.deployments;")
                row = cur.fetchone()
                return row[0] if row else 0
        except Exception:
            return 0
        finally:
            if conn is not None:
                self.release_connection(conn)

    def get_recent_deployments(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns recent deployments from PostgreSQL 18."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT * FROM {self.config.target_schema}.deployments
                    ORDER BY deployed_at DESC LIMIT %s;
                """, (limit,))
                return [dict(r) for r in cur.fetchall()]
        except Exception:
            return []
        finally:
            if conn is not None:
                self.release_connection(conn)
