"""Configuration settings for Google Sheets & Airtable Two-Way Sync Daemon.
Zero em dash policy enforced.
"""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class SheetsAirtableSyncConfig:
    pg_host: str = "127.0.0.1"
    pg_port: int = 5433
    pg_user: str = "postgres"
    pg_password: str = "postgres"
    pg_database: str = "postgres"
    target_schema: str = "e18_sheets_airtable_sync"
    rate_limit_rps: float = 5.0
    token_bucket_capacity: int = 10
    default_conflict_strategy: str = "TIMESTAMP_PRECEDENCE"
    polling_interval_seconds: int = 30
    sqlite_db_path: str = "sheets_airtable_sync.db"
    max_memory_mb_cap: float = 250.0

    def get_pg_connection_dict(self) -> Dict[str, Any]:
        return {
            "host": self.pg_host,
            "port": self.pg_port,
            "user": self.pg_user,
            "password": self.pg_password,
            "database": self.pg_database,
            "connect_timeout": 5
        }
