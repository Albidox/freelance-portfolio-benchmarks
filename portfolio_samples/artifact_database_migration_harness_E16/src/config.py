"""Configuration settings for Enterprise Database Migration Harness.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class DatabaseMigrationConfig:
    source_type: str = "MYSQL"
    source_connection_string: str = "sqlite:///:memory:"
    pg_host: str = "127.0.0.1"
    pg_port: int = 5433
    pg_user: str = "postgres"
    pg_password: str = "postgres"
    pg_database: str = "postgres"
    target_schema: str = "e16_db_migration"
    batch_size: int = 5000
    max_workers: int = 4
    connection_timeout_seconds: float = 8.0
    retry_max_attempts: int = 3
    retry_backoff_factor: float = 1.5
    retry_jitter_enabled: bool = True
    quarantine_corrupt_data: bool = True
    enable_wal_checkpoint: bool = True
    sqlite_audit_path: str = "migration_checkpoint.db"
    max_memory_mb_cap: float = 250.0

    def get_pg_connection_dict(self) -> Dict[str, Any]:
        return {
            "host": self.pg_host,
            "port": self.pg_port,
            "user": self.pg_user,
            "password": self.pg_password,
            "database": self.pg_database,
            "connect_timeout": int(self.connection_timeout_seconds)
        }
