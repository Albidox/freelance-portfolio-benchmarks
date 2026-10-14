"""Storage persistence engine supporting Native PostgreSQL 18 and SQLite WAL.
Enforces zero em dash policy.
"""
import sqlite3
import json
from typing import Dict, Any, Optional
from src.config import ADBBotConfig
from src.models import WorkflowRun


class ADBBotStorage:
    """Storage coordinator managing SQLite WAL cache and PostgreSQL DDL generation."""

    def __init__(self, config: ADBBotConfig):
        self.config = config

    def init_sqlite_cache(self) -> None:
        """Initialize local SQLite WAL database for high-throughput mobile telemetry."""
        with sqlite3.connect(self.config.sqlite_cache_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    run_id TEXT PRIMARY KEY,
                    workflow_name TEXT NOT NULL,
                    total_steps INTEGER NOT NULL,
                    successful_steps INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS match_metrics (
                    metric_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    template_name TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    matched_scale REAL NOT NULL,
                    captured_at TEXT NOT NULL
                );
            """)
            conn.commit()

    def record_run_sqlite(self, run: WorkflowRun) -> bool:
        """Persist workflow run into SQLite cache."""
        with sqlite3.connect(self.config.sqlite_cache_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO workflow_runs (
                    run_id, workflow_name, total_steps, successful_steps, status, started_at, ended_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                run.run_id,
                run.workflow_name,
                run.total_steps,
                run.successful_steps,
                run.status,
                run.started_at,
                run.ended_at
            ))
            conn.commit()
        return True

    def record_metric_sqlite(
        self,
        metric_id: str,
        run_id: str,
        template_name: str,
        confidence: float,
        matched_scale: float,
        captured_at: str
    ) -> bool:
        """Persist individual match metric into SQLite cache."""
        with sqlite3.connect(self.config.sqlite_cache_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO match_metrics (
                    metric_id, run_id, template_name, confidence, matched_scale, captured_at
                ) VALUES (?, ?, ?, ?, ?, ?);
            """, (
                metric_id,
                run_id,
                template_name,
                confidence,
                matched_scale,
                captured_at
            ))
            conn.commit()
        return True

    def get_postgres_schema_ddl(self) -> str:
        """Return PostgreSQL 18 DDL for dynamic schema isolation."""
        return f"""
        CREATE SCHEMA IF NOT EXISTS {self.config.db_schema};
        CREATE TABLE IF NOT EXISTS {self.config.db_schema}.workflow_runs (
            run_id VARCHAR(64) PRIMARY KEY,
            workflow_name VARCHAR(128) NOT NULL,
            total_steps INTEGER NOT NULL,
            successful_steps INTEGER NOT NULL,
            status VARCHAR(32) NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            ended_at TIMESTAMPTZ
        );
        CREATE TABLE IF NOT EXISTS {self.config.db_schema}.match_metrics (
            metric_id VARCHAR(64) PRIMARY KEY,
            run_id VARCHAR(64) NOT NULL,
            template_name VARCHAR(128) NOT NULL,
            confidence NUMERIC(6, 4) NOT NULL,
            matched_scale NUMERIC(4, 2) NOT NULL,
            captured_at TIMESTAMPTZ NOT NULL
        );
        """
