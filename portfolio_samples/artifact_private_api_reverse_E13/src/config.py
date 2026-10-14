"""Configuration settings for Private Mobile & SPA Reverse Engineering Engine.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class PrivateApiConfig:
    base_url: str = "https://api.internal-target.com"
    timeout_seconds: float = 10.0
    max_retries: int = 3
    base_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 16.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_recovery_seconds: float = 30.0
    sqlite_db_path: str = "private_api_harvest.db"
    pg_host: str = "127.0.0.1"
    pg_port: int = 5433
    pg_user: str = "postgres"
    pg_password: str = "postgres"
    pg_database: str = "freelance_db"
    pg_schema: str = "e13_private_api"
    proxy_urls: List[str] = field(default_factory=lambda: [
        "http://proxy1.internal.local:8080",
        "http://proxy2.internal.local:8080"
    ])
    default_salt: str = "SALT_V2"
    api_secret: str = "prod_mobile_key_2026"
    request_timeout: float = 10.0
