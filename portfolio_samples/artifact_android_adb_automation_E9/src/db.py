"""PostgreSQL 18 persistence and schema isolation manager for Android ADB Bot.
Enforces zero em dash policy.
"""
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import execute_batch
from src.config import ADBBotConfig
from src.models import WorkflowRun


class DatabaseManager:
    """PostgreSQL 18 database interface for dynamic schema isolation and high-volume execution logging."""

    def __init__(self, config: Optional[ADBBotConfig] = None):
        self.config = config or ADBBotConfig()

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
                    CREATE TABLE IF NOT EXISTS {self.config.db_schema}.workflow_runs (
                        run_id VARCHAR(64) PRIMARY KEY,
                        workflow_name VARCHAR(128) NOT NULL,
                        total_steps INTEGER NOT NULL,
                        successful_steps INTEGER NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        started_at TIMESTAMPTZ NOT NULL,
                        ended_at TIMESTAMPTZ
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.db_schema}.match_metrics (
                        metric_id VARCHAR(64) PRIMARY KEY,
                        run_id VARCHAR(64) NOT NULL,
                        template_name VARCHAR(128) NOT NULL,
                        confidence NUMERIC(6, 4) NOT NULL,
                        matched_scale NUMERIC(4, 2) NOT NULL,
                        captured_at TIMESTAMPTZ NOT NULL
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.db_schema}.execution_logs (
                        log_id SERIAL PRIMARY KEY,
                        run_id VARCHAR(64) NOT NULL,
                        step_id VARCHAR(64) NOT NULL,
                        action_type VARCHAR(32) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        details TEXT,
                        executed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    );
                """)
            conn.commit()

    def record_run(self, run: WorkflowRun) -> bool:
        """Persist workflow run into PostgreSQL 18."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.db_schema}.workflow_runs (
                        run_id, workflow_name, total_steps, successful_steps, status, started_at, ended_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        successful_steps = EXCLUDED.successful_steps,
                        ended_at = EXCLUDED.ended_at;
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

    def batch_insert_metrics(self, metrics: List[Dict[str, Any]]) -> int:
        """Stream batch of match metrics into PostgreSQL using execute_batch."""
        sql = f"""
            INSERT INTO {self.config.db_schema}.match_metrics (
                metric_id, run_id, template_name, confidence, matched_scale, captured_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (metric_id) DO UPDATE SET
                confidence = EXCLUDED.confidence;
        """
        data = [
            (
                m["metric_id"],
                m["run_id"],
                m["template_name"],
                m["confidence"],
                m["matched_scale"],
                m["captured_at"]
            )
            for m in metrics
        ]
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                execute_batch(cur, sql, data, page_size=1000)
            conn.commit()
        return len(data)

    def log_execution(
        self,
        run_id: str,
        step_id: str,
        action_type: str,
        status: str,
        details: str = ""
    ) -> bool:
        """Append execution step event log to PostgreSQL 18."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.config.db_schema}.execution_logs (
                        run_id, step_id, action_type, status, details
                    ) VALUES (%s, %s, %s, %s, %s);
                """, (run_id, step_id, action_type, status, details))
            conn.commit()
        return True
