"""Configuration settings for Remote PC Maintenance and Windows Optimization Toolkit.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class WindowsOptimizerConfig:
    min_disk_free_gb_threshold: float = 10.0
    safe_cleanup_days_threshold: int = 1
    protected_services: List[str] = field(default_factory=lambda: [
        "wuauserv", "BITS", "CryptSvc", "DcomLaunch", "RpcSs",
        "RpcEptMapper", "EventLog", "PlugPlay", "Dhcp", "Dnscache"
    ])
    sqlite_db_path: str = "windows_optimization_audit.db"
    pg_host: str = "127.0.0.1"
    pg_port: int = 5433
    pg_user: str = "postgres"
    pg_password: str = "postgres"
    pg_database: str = "freelance_db"
    pg_schema: str = "e14_pc_cleanup"
