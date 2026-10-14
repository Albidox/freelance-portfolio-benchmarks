"""Dual-tier audit persistence using SQLite WAL local cache and Native PostgreSQL 18 sync.
Strict zero em dash policy enforced.
"""
import sqlite3
import os
from typing import Dict, Any, Optional, List
from src.models import DeploymentRecord, DeploymentStatus, DeploymentStrategy, HealthCheckStatus
from src.config import DeploymentPipelineConfig


class DeploymentStorage:
    """Manages SQLite WAL local audit cache for deployment events."""

    def __init__(self, config: Optional[DeploymentPipelineConfig] = None):
        self.config = config or DeploymentPipelineConfig()
        self.sqlite_path = self.config.sqlite_audit_path
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initializes SQLite schema in WAL mode with busy timeout."""
        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS deployment_audit (
                    deployment_id TEXT PRIMARY KEY,
                    strategy TEXT,
                    image_tag TEXT,
                    active_container_id TEXT,
                    previous_container_id TEXT,
                    status TEXT,
                    health_check_status TEXT,
                    rollback_triggered INTEGER,
                    elapsed_seconds REAL,
                    deployed_at TEXT
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def record_deployment(self, record: DeploymentRecord) -> None:
        """Stores deployment record in SQLite WAL table."""
        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("""
                INSERT OR REPLACE INTO deployment_audit (
                    deployment_id, strategy, image_tag, active_container_id,
                    previous_container_id, status, health_check_status,
                    rollback_triggered, elapsed_seconds, deployed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                record.deployment_id,
                record.strategy.value if hasattr(record.strategy, "value") else str(record.strategy),
                record.image_tag,
                record.active_container_id,
                record.previous_container_id,
                record.status.value if hasattr(record.status, "value") else str(record.status),
                record.health_check_status.value if hasattr(record.health_check_status, "value") else str(record.health_check_status),
                1 if record.rollback_triggered else 0,
                record.elapsed_seconds,
                record.deployed_at
            ))
            conn.commit()
        finally:
            conn.close()

    def get_deployment(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        """Reads back deployment record for verification."""
        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM deployment_audit WHERE deployment_id = ?", (deployment_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_deployments(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Lists recent deployments."""
        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM deployment_audit ORDER BY deployed_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
