"""Data contracts, models, and enums for Remote PC Maintenance & Windows Optimization Toolkit.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


class CleanTargetType(str, Enum):
    WINDOWS_TEMP = "WINDOWS_TEMP"
    USER_TEMP = "USER_TEMP"
    SOFTWARE_DISTRIBUTION = "SOFTWARE_DISTRIBUTION"
    CRASH_DUMPS = "CRASH_DUMPS"
    BROWSER_CACHE = "BROWSER_CACHE"
    RECYCLE_BIN = "RECYCLE_BIN"


class OptimizationAction(str, Enum):
    ANALYZE = "ANALYZE"
    DRY_RUN = "DRY_RUN"
    PURGE = "PURGE"
    DISABLE = "DISABLE"
    ROLLBACK = "ROLLBACK"


class ServiceStartupType(str, Enum):
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    DISABLED = "DISABLED"
    DELAYED_AUTO = "DELAYED_AUTO"
    UNKNOWN = "UNKNOWN"


@dataclass
class CleanupRule:
    target_type: CleanTargetType
    target_path: str
    file_extensions: List[str] = field(default_factory=lambda: ["*.*"])
    max_age_days: int = 0
    dry_run: bool = True
    recursive: bool = True


@dataclass
class CleanupResult:
    target_type: CleanTargetType
    target_path: str
    files_scanned: int = 0
    files_deleted: int = 0
    bytes_reclaimed: int = 0
    locked_files_skipped: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def megabytes_reclaimed(self) -> float:
        return round(self.bytes_reclaimed / (1024 * 1024), 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_type": self.target_type.value,
            "target_path": self.target_path,
            "files_scanned": self.files_scanned,
            "files_deleted": self.files_deleted,
            "bytes_reclaimed": self.bytes_reclaimed,
            "megabytes_reclaimed": self.megabytes_reclaimed,
            "locked_files_skipped": self.locked_files_skipped,
            "errors_count": len(self.errors)
        }


@dataclass
class ServiceAuditRecord:
    service_name: str
    display_name: str
    current_startup: ServiceStartupType
    current_status: str
    recommended_startup: ServiceStartupType
    is_safe_to_disable: bool
    category: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "display_name": self.display_name,
            "current_startup": self.current_startup.value,
            "current_status": self.current_status,
            "recommended_startup": self.recommended_startup.value,
            "is_safe_to_disable": self.is_safe_to_disable,
            "category": self.category,
            "reason": self.reason
        }


@dataclass
class RegistryAuditRecord:
    hive: str
    key_path: str
    value_name: str
    issue_type: str
    recommended_action: str
    backup_command: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SystemHealthSnapshot:
    cpu_usage_pct: float
    ram_total_gb: float
    ram_used_gb: float
    ram_percent: float
    disk_total_gb: float
    disk_free_gb: float
    disk_free_pct: float
    health_score: int
    captured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiskCleanTarget:
    name: str
    path: str
    target_type: CleanTargetType
    description: str = ""
    safe_to_purge: bool = True
    estimated_size_bytes: int = 0
    file_extensions: List[str] = field(default_factory=lambda: ["*.*"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "target_type": self.target_type.value,
            "description": self.description,
            "safe_to_purge": self.safe_to_purge,
            "estimated_size_bytes": self.estimated_size_bytes,
            "file_extensions": self.file_extensions
        }


@dataclass
class ServiceTuningRule:
    service_name: str
    target_startup: ServiceStartupType
    rationale: str
    category: str = "Optimization"
    requires_admin: bool = True
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "target_startup": self.target_startup.value,
            "rationale": self.rationale,
            "category": self.category,
            "requires_admin": self.requires_admin,
            "dependencies": self.dependencies
        }


@dataclass
class HealthScanResult:
    scan_type: str  # SFC or DISM
    corrupted_files_found: bool = False
    repair_successful: bool = True
    log_summary: str = ""
    duration_seconds: float = 0.0
    scanned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OptimizationReport:
    total_bytes_reclaimed: int = 0
    total_files_deleted: int = 0
    locked_files_skipped: int = 0
    services_audited: int = 0
    services_optimized: int = 0
    registry_keys_audited: int = 0
    health_score_before: int = 0
    health_score_after: int = 0
    scan_results: List[HealthScanResult] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def megabytes_reclaimed(self) -> float:
        return round(self.total_bytes_reclaimed / (1024 * 1024), 2)

    @property
    def gigabytes_reclaimed(self) -> float:
        return round(self.total_bytes_reclaimed / (1024 * 1024 * 1024), 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes_reclaimed": self.total_bytes_reclaimed,
            "megabytes_reclaimed": self.megabytes_reclaimed,
            "gigabytes_reclaimed": self.gigabytes_reclaimed,
            "total_files_deleted": self.total_files_deleted,
            "locked_files_skipped": self.locked_files_skipped,
            "services_audited": self.services_audited,
            "services_optimized": self.services_optimized,
            "registry_keys_audited": self.registry_keys_audited,
            "health_score_before": self.health_score_before,
            "health_score_after": self.health_score_after,
            "scan_results_count": len(self.scan_results),
            "created_at": self.created_at
        }
