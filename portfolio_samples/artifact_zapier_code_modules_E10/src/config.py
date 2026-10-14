"""Runtime configuration and database connection factory.
Strict zero em dash policy enforced.
"""
import os
from dataclasses import dataclass


@dataclass
class ZapierModulesConfig:
    environment: str = os.getenv("EXEC_ENV", "LOCAL_CLI")
    sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", "zapier_modules.db")
    pg_host: str = os.getenv("PG_HOST", "127.0.0.1")
    pg_port: int = int(os.getenv("PG_PORT", "5433"))
    pg_user: str = os.getenv("PG_USER", "postgres")
    pg_password: str = os.getenv("PG_PASSWORD", "postgres")
    pg_database: str = os.getenv("PG_DATABASE", "postgres")
    pg_schema: str = os.getenv("PG_SCHEMA", "e10_zapier_modules")
    max_memory_mb: int = 250
    serverless_duration_cap_ms: int = 9500
