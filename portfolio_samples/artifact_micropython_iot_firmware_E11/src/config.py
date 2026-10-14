"""Host and target runtime configuration for MicroPython IoT system.
Strict zero em dash policy enforced.
"""
import os
from dataclasses import dataclass


@dataclass
class IoTFirmwareConfig:
    device_uuid: str = os.getenv("DEVICE_UUID", "esp32-node-001")
    sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", "iot_telemetry.db")
    pg_host: str = os.getenv("PG_HOST", "127.0.0.1")
    pg_port: int = int(os.getenv("PG_PORT", "5433"))
    pg_user: str = os.getenv("PG_USER", "postgres")
    pg_password: str = os.getenv("PG_PASSWORD", "postgres")
    pg_database: str = os.getenv("PG_DATABASE", "postgres")
    pg_schema: str = os.getenv("PG_SCHEMA", "e11_micropython_iot")
    max_memory_mb: int = 250
    target_heap_limit_kb: int = 128
