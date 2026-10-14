"""Configuration settings for WordPress and WooCommerce Database Tuning Engine.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class WordPressOptimizerConfig:
    table_prefix: str = "wp_"
    max_autoload_kb_threshold: float = 800.0  # 800 KB recommended threshold
    slow_query_ms_threshold: float = 100.0  # 100 ms query execution threshold
    batch_purge_limit: int = 1000  # chunked commit batch size
    dry_run: bool = True
    sqlite_db_path: str = "wordpress_db_tuning.db"
    pg_host: str = "127.0.0.1"
    pg_port: int = 5433
    pg_user: str = "postgres"
    pg_password: str = "postgres"
    pg_database: str = "freelance_db"
    pg_schema: str = "e15_wp_db_opt"
