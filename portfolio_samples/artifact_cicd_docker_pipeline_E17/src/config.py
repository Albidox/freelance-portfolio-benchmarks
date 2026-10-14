"""Configuration settings for Containerization & CI/CD Deployment Automation.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class DeploymentPipelineConfig:
    pg_host: str = "127.0.0.1"
    pg_port: int = 5433
    pg_user: str = "postgres"
    pg_password: str = "postgres"
    pg_database: str = "postgres"
    target_schema: str = "e17_cicd_pipeline"
    default_strategy: str = "BLUE_GREEN"
    health_check_timeout_seconds: float = 10.0
    health_check_probe_interval_seconds: float = 1.0
    max_health_probe_retries: int = 5
    max_rollback_retries: int = 2
    sqlite_audit_path: str = "cicd_deployment_audit.db"
    max_memory_mb_cap: float = 250.0

    def get_pg_connection_dict(self) -> Dict[str, Any]:
        return {
            "host": self.pg_host,
            "port": self.pg_port,
            "user": self.pg_user,
            "password": self.pg_password,
            "dbname": self.pg_database,
            "connect_timeout": 5
        }
