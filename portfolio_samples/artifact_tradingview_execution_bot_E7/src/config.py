"""Configuration settings for TradingView Execution Bot."""
import os
from dataclasses import dataclass, field
from typing import List

@dataclass(frozen=True)
class TradingBotConfig:
    db_host: str = os.getenv("PGHOST", "127.0.0.1")
    db_port: int = int(os.getenv("PGPORT", "5433"))
    db_user: str = os.getenv("PGUSER", "postgres")
    db_password: str = os.getenv("PGPASSWORD", "postgres")
    db_name: str = os.getenv("PGDATABASE", "postgres")
    db_schema: str = os.getenv("PGSCHEMA", "e7_tradingview_bot")

    webhook_passphrase: str = os.getenv("WEBHOOK_PASSPHRASE", "TvSecretAlertPass2026")
    webhook_secret_key: str = os.getenv("WEBHOOK_SECRET_KEY", "tv_hmac_secret_key_prod_9988")
    sqlite_cache_path: str = os.getenv("SQLITE_CACHE_PATH", "tradingbot_cache.db")

    allowed_tradingview_ips: List[str] = field(default_factory=lambda: [
        "52.89.214.238",
        "34.212.75.30",
        "54.218.53.128",
        "52.32.178.7",
        "127.0.0.1"
    ])

    max_slippage_bps: int = int(os.getenv("MAX_SLIPPAGE_BPS", "50"))
    max_memory_mb: int = int(os.getenv("MAX_MEMORY_MB", "250"))
    order_timeout_ms: int = int(os.getenv("ORDER_TIMEOUT_MS", "5000"))
