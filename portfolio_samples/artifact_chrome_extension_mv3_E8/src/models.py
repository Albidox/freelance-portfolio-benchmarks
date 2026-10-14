"""Data contracts, models, and enums for Chrome Data Exporter Extension."""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


class ExportFormat(str, Enum):
    CSV = "CSV"
    JSON = "JSON"
    NDJSON = "NDJSON"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    SCRAPING = "SCRAPING"
    SANITIZING = "SANITIZING"
    EXPORTING = "EXPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class ColumnMapping:
    source_field: str
    target_column: str
    is_required: bool = True
    default_value: str = ""
    transform_strip: bool = True


@dataclass
class ScrapeRule:
    rule_id: str
    domain_pattern: str
    row_selector: str
    column_selectors: Dict[str, str]
    pagination_selector: Optional[str] = None
    max_pages: int = 10
    wait_after_scroll_ms: int = 1500

    def validate(self) -> bool:
        """Validate presence of required selector fields."""
        if not self.rule_id or not self.domain_pattern:
            return False
        if not self.row_selector or not self.column_selectors:
            return False
        return True


@dataclass
class ExportRecord:
    record_id: str
    source_url: str
    extracted_data: Dict[str, Any]
    captured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class BatchExportJob:
    job_id: str
    rule_id: str
    format: ExportFormat
    total_records: int
    status: JobStatus
    chunk_size: int = 2000
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "rule_id": self.rule_id,
            "format": self.format.value,
            "total_records": self.total_records,
            "status": self.status.value,
            "chunk_size": self.chunk_size,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }
