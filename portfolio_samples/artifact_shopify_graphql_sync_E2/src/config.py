"""Configuration definitions for Shopify synchronization."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ShopifySyncConfig:
    shop_domain: str = os.getenv("SHOPIFY_SHOP_DOMAIN", "mystore.myshopify.com")
    access_token: str = os.getenv("SHOPIFY_ACCESS_TOKEN", "shpat_test_token_123")
    api_version: str = os.getenv("SHOPIFY_API_VERSION", "2024-01")

    db_host: str = os.getenv("PGHOST", "127.0.0.1")
    db_port: int = int(os.getenv("PGPORT", "5433"))
    db_user: str = os.getenv("PGUSER", "postgres")
    db_password: str = os.getenv("PGPASSWORD", "postgres")
    db_name: str = os.getenv("PGDATABASE", "postgres")
    db_schema: str = os.getenv("PGSCHEMA", "sandbox_e2")

    sqlite_state_path: str = os.getenv("SQLITE_STATE_PATH", "catalog_sync_state.db")
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "15.0"))
    max_memory_mb: int = int(os.getenv("MAX_MEMORY_MB", "250"))
