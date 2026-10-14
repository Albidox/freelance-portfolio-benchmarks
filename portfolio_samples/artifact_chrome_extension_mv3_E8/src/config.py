"""Configuration settings for Chrome Data Exporter Extension."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtensionExporterConfig:
    db_host: str = os.getenv("PGHOST", "127.0.0.1")
    db_port: int = int(os.getenv("PGPORT", "5433"))
    db_user: str = os.getenv("PGUSER", "postgres")
    db_password: str = os.getenv("PGPASSWORD", "postgres")
    db_name: str = os.getenv("PGDATABASE", "postgres")
    db_schema: str = os.getenv("PGSCHEMA", "e8_extension_exporter")

    sqlite_cache_path: str = os.getenv("SQLITE_CACHE_PATH", "extension_cache.db")
    max_memory_mb: int = int(os.getenv("MAX_MEMORY_MB", "250"))
    batch_chunk_size: int = int(os.getenv("BATCH_CHUNK_SIZE", "2000"))
    max_records_per_export: int = int(os.getenv("MAX_RECORDS_PER_EXPORT", "50000"))
