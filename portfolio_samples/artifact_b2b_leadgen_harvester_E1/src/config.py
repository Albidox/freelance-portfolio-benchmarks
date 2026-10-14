"""System configuration and environment parameters for B2B Lead Harvester.
Strict zero em dash policy enforced.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class HarvesterConfig:
    db_host: str = os.getenv("PGHOST", "127.0.0.1")
    db_port: int = int(os.getenv("PGPORT", "5433"))
    db_user: str = os.getenv("PGUSER", "postgres")
    db_password: str = os.getenv("PGPASSWORD", "postgres")
    db_name: str = os.getenv("PGDATABASE", "postgres")
    db_schema: str = os.getenv("PGSCHEMA", "sandbox_e1")

    sqlite_cache_path: str = os.getenv("SQLITE_CACHE_PATH", "leadgen_cache.db")
    max_concurrency: int = int(os.getenv("MAX_CONCURRENCY", "10"))
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT", "15.0"))
    rate_limit_per_second: float = float(os.getenv("RATE_LIMIT", "20.0"))
    max_memory_mb: int = int(os.getenv("MAX_MEMORY_MB", "250"))

    proxy_urls: tuple = (
        "http://proxy1.internal:8080",
        "http://proxy2.internal:8080",
    )

    disposable_domains: tuple = (
        "tempmail.com", "mailinator.com", "guerrillamail.com", "10minutemail.com"
    )
