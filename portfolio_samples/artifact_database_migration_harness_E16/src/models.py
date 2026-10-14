"""Data contracts, models, and enums for Enterprise Database Migration Harness.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import hashlib
import json


class MigrationSourceType(str, Enum):
    MYSQL = "MYSQL"
    MONGODB = "MONGODB"
    SQLITE = "SQLITE"
    POSTGRES = "POSTGRES"


class MigrationStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"


class TargetDataType(str, Enum):
    BIGINT = "BIGINT"
    INTEGER = "INTEGER"
    VARCHAR = "VARCHAR"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"
    TIMESTAMP = "TIMESTAMP WITH TIME ZONE"
    NUMERIC = "NUMERIC"
    JSONB = "JSONB"


@dataclass
class ColumnMapping:
    source_field: str
    target_column: str
    target_type: TargetDataType
    is_primary_key: bool = False
    is_nullable: bool = True
    default_value: Optional[Any] = None


@dataclass
class MigrationRecord:
    source_id: str
    data: Dict[str, Any]
    checksum: str = ""

    def calculate_checksum(self) -> str:
        serialized = json.dumps(self.data, sort_keys=True, default=str)
        self.checksum = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return self.checksum


@dataclass
class MigrationBatch:
    batch_id: int
    source_type: MigrationSourceType
    table_name: str
    records: List[MigrationRecord] = field(default_factory=list)
    start_offset: int = 0
    end_offset: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def record_count(self) -> int:
        return len(self.records)


@dataclass
class QuarantineRecord:
    source_id: str
    raw_payload: str
    failure_reason: str
    quarantined_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReconciliationReport:
    table_name: str
    source_total_count: int
    target_total_count: int
    source_checksum_root: str
    target_checksum_root: str
    missing_in_target: int
    data_mismatches: int
    is_verified: bool
    reconciliation_time_ms: float
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MigrationAuditLog:
    run_id: str
    source_type: str
    target_schema: str
    table_name: str
    total_migrated: int
    quarantined_count: int
    elapsed_seconds: float
    status: MigrationStatus
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChunkProgress:
    chunk_id: int
    table_name: str
    start_offset: int
    end_offset: int
    total_records: int
    processed_records: int
    memory_used_mb: float = 0.0
    is_completed: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConsistencyReport:
    table_name: str
    source_checksum: str
    target_checksum: str
    records_evaluated: int
    is_consistent: bool
    discrepancies_count: int = 0
    audit_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChecksumManifest:
    manifest_id: str
    table_name: str
    row_count: int
    root_sha256: str
    chunk_hashes: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
