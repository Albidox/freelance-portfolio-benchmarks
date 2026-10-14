"""Data contracts, models, and enums for Google Sheets & Airtable Two-Way Sync Daemon.
Zero em dash policy enforced.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import hashlib
import json


class SyncDirection(str, Enum):
    SHEETS_TO_AIRTABLE = "SHEETS_TO_AIRTABLE"
    AIRTABLE_TO_SHEETS = "AIRTABLE_TO_SHEETS"
    BIDIRECTIONAL = "BIDIRECTIONAL"


class ConflictStrategy(str, Enum):
    TIMESTAMP_PRECEDENCE = "TIMESTAMP_PRECEDENCE"
    SHEETS_WINS = "SHEETS_WINS"
    AIRTABLE_WINS = "AIRTABLE_WINS"
    FIELD_LEVEL_MERGE = "FIELD_LEVEL_MERGE"


class ChangeType(str, Enum):
    ADDED = "ADDED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"
    UNCHANGED = "UNCHANGED"


@dataclass
class SyncRecordItem:
    entity_id: str
    fields: Dict[str, Any]
    last_modified: str
    formula_fields: Dict[str, str] = field(default_factory=dict)
    fingerprint: str = ""

    def calculate_fingerprint(self) -> str:
        # Exclude last_modified timestamp from fingerprint to track pure data drift
        clean_fields = {k: v for k, v in self.fields.items() if k != "last_modified"}
        serialized = json.dumps(clean_fields, sort_keys=True, default=str)
        self.fingerprint = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return self.fingerprint


@dataclass
class ChangeDelta:
    entity_id: str
    change_type: ChangeType
    source: str
    previous_data: Optional[Dict[str, Any]] = None
    new_data: Optional[Dict[str, Any]] = None


# Alias for compatibility with execution directives
RecordDelta = ChangeDelta


@dataclass
class ConflictResolutionResult:
    entity_id: str
    strategy_applied: ConflictStrategy
    resolved_fields: Dict[str, Any]
    winning_source: str
    quarantined: bool = False
    quarantine_reason: Optional[str] = None


@dataclass
class SyncCycleReport:
    cycle_id: str
    direction: SyncDirection
    records_scanned: int
    records_added: int
    records_updated: int
    records_deleted: int
    conflicts_resolved: int
    conflicts_quarantined: int
    elapsed_seconds: float
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Alias for compatibility with execution directives
SyncReport = SyncCycleReport


@dataclass
class SyncBatch:
    batch_id: str
    records: List[SyncRecordItem]
    source: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_count: int = 0

    def __post_init__(self):
        if not self.total_count:
            self.total_count = len(self.records)


@dataclass
class ProviderCredentials:
    provider: str
    api_key: str
    base_id: Optional[str] = None
    spreadsheet_id: Optional[str] = None
    token_type: str = "Bearer"
    endpoint_url: Optional[str] = None
