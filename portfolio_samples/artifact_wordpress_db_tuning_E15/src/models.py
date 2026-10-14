"""Data contracts, models, and enums for WordPress and WooCommerce Database Optimization.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


class TableType(str, Enum):
    WP_POSTS = "wp_posts"
    WP_POSTMETA = "wp_postmeta"
    WP_OPTIONS = "wp_options"
    WP_COMMENTS = "wp_comments"
    WP_COMMENTMETA = "wp_commentmeta"
    WP_WC_ORDER_STATS = "wp_wc_order_stats"


class OptimizationSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class QueryProfileRecord:
    query_sql: str
    execution_time_ms: float
    rows_examined: int
    rows_sent: int
    is_full_table_scan: bool
    uses_filesort: bool
    uses_temporary_table: bool
    bottleneck_severity: OptimizationSeverity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_sql": self.query_sql,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "rows_examined": self.rows_examined,
            "rows_sent": self.rows_sent,
            "is_full_table_scan": self.is_full_table_scan,
            "uses_filesort": self.uses_filesort,
            "uses_temporary_table": self.uses_temporary_table,
            "bottleneck_severity": self.bottleneck_severity.value
        }


@dataclass
class SlowQueryLog:
    query_sql: str
    execution_time_ms: float
    rows_examined: int
    rows_sent: int
    severity: str
    logged_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AutoloadOptionItem:
    option_name: str
    option_size_bytes: int
    is_transient: bool
    current_autoload: str
    recommended_autoload: str
    plugin_guess: str

    @property
    def size_kb(self) -> float:
        return round(self.option_size_bytes / 1024.0, 2)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["size_kb"] = self.size_kb
        return data


@dataclass
class TransientPurgeTarget:
    option_name: str
    option_size_bytes: int
    is_expired: bool
    timeout_timestamp: int = 0
    purge_reason: str = "expired transient"

    @property
    def size_kb(self) -> float:
        return round(self.option_size_bytes / 1024.0, 2)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["size_kb"] = self.size_kb
        return data


@dataclass
class IndexRecommendation:
    table_name: str
    index_name: str
    target_columns: List[str]
    is_composite: bool
    prefix_length_clamped: bool
    estimated_speedup_pct: float
    ddl_statement: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrphanCleanupSummary:
    table_name: str
    orphaned_rows_found: int
    purged_rows: int
    bytes_reclaimed: int
    purge_batch_size: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DbHealthReport:
    total_autoload_kb: float
    slow_queries_count: int
    missing_indexes_count: int
    orphaned_records_count: int
    health_score: int
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OptimizationReport:
    total_autoload_kb: float
    slow_queries_count: int
    missing_indexes_count: int
    orphaned_records_count: int
    health_score: int
    recommendations: List[IndexRecommendation] = field(default_factory=list)
    purge_summaries: List[OrphanCleanupSummary] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_autoload_kb": self.total_autoload_kb,
            "slow_queries_count": self.slow_queries_count,
            "missing_indexes_count": self.missing_indexes_count,
            "orphaned_records_count": self.orphaned_records_count,
            "health_score": self.health_score,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "purge_summaries": [s.to_dict() for s in self.purge_summaries],
            "generated_at": self.generated_at
        }
