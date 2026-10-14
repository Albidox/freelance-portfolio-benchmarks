"""System configuration and environment parameters for Amazon SP-API Tracker."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SPAPIConfig:
    """Configuration settings for Amazon SP-API connection, AWS SigV4, and databases."""

    db_host: str = os.getenv("PGHOST", "127.0.0.1")
    db_port: int = int(os.getenv("PGPORT", "5433"))
    db_user: str = os.getenv("PGUSER", "postgres")
    db_password: str = os.getenv("PGPASSWORD", "postgres")
    db_name: str = os.getenv("PGDATABASE", "postgres")
    db_schema: str = os.getenv("PGSCHEMA", "e6_spapi_tracker")

    lwa_app_id: str = os.getenv("LWA_APP_ID", "amzn1.application-oa2-client.dummy123")
    lwa_client_secret: str = os.getenv("LWA_CLIENT_SECRET", "dummy_client_secret_xyz789")
    lwa_refresh_token: str = os.getenv("LWA_REFRESH_TOKEN", "Atzr|dummy_refresh_token_abc")
    aws_access_key: str = os.getenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    aws_secret_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    marketplace_id: str = os.getenv("AMAZON_MARKETPLACE_ID", "ATVPDKIKX0DER")

    sqlite_cache_path: str = os.getenv("SQLITE_CACHE_PATH", "spapi_cache.db")
    rate_limit_rps: float = float(os.getenv("RATE_LIMIT_RPS", "5.0"))
    max_memory_mb: int = int(os.getenv("MAX_MEMORY_MB", "250"))
    batch_asin_size: int = int(os.getenv("BATCH_ASIN_SIZE", "20"))
