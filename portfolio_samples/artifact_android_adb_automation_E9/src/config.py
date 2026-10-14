"""Configuration settings for Android ADB and OpenCV Automation Bot.
Enforces zero em dash policy.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ADBBotConfig:
    db_host: str = os.getenv("PGHOST", "127.0.0.1")
    db_port: int = int(os.getenv("PGPORT", "5433"))
    db_user: str = os.getenv("PGUSER", "postgres")
    db_password: str = os.getenv("PGPASSWORD", "postgres")
    db_name: str = os.getenv("PGDATABASE", "postgres")
    db_schema: str = os.getenv("PGSCHEMA", "e9_android_bot")

    adb_path: str = os.getenv("ADB_PATH", "adb")
    device_serial: str = os.getenv("DEVICE_SERIAL", "emulator-5554")
    sqlite_cache_path: str = os.getenv("SQLITE_CACHE_PATH", "android_bot.db")

    default_match_threshold: float = float(os.getenv("DEFAULT_MATCH_THRESHOLD", "0.85"))
    human_jitter_radius_px: int = int(os.getenv("HUMAN_JITTER_RADIUS_PX", "12"))
    max_reconnect_attempts: int = int(os.getenv("MAX_RECONNECT_ATTEMPTS", "5"))
    max_memory_mb: int = int(os.getenv("MAX_MEMORY_MB", "250"))
