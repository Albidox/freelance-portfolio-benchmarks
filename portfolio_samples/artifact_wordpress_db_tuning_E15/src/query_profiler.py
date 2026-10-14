"""Slow query analyzer and MySQL EXPLAIN execution plan inspector.
Strict zero em dash policy enforced.
"""
import re
from typing import Dict, Any, List, Optional
from src.models import QueryProfileRecord, OptimizationSeverity
from src.config import WordPressOptimizerConfig


class QueryProfiler:
    def __init__(self, config: Optional[WordPressOptimizerConfig] = None):
        self.config = config or WordPressOptimizerConfig()

    def classify_bottleneck(
        self,
        execution_time_ms: float,
        rows_examined: int,
        rows_sent: int,
        is_full_table_scan: bool,
        uses_filesort: bool
    ) -> OptimizationSeverity:
        """Classify optimization urgency based on examined-to-sent ratio and execution time."""
        if execution_time_ms >= 500.0 or (is_full_table_scan and rows_examined > 50000):
            return OptimizationSeverity.CRITICAL
        elif execution_time_ms >= self.config.slow_query_ms_threshold or uses_filesort:
            return OptimizationSeverity.HIGH
        elif rows_examined > (rows_sent * 100) and rows_examined > 5000:
            return OptimizationSeverity.MEDIUM
        return OptimizationSeverity.LOW

    def profile_query(
        self,
        query_sql: str,
        execution_time_ms: float,
        rows_examined: int,
        rows_sent: int,
        explain_plan: Optional[List[Dict[str, Any]]] = None
    ) -> QueryProfileRecord:
        """Analyze SQL query and EXPLAIN details to construct a diagnostic record."""
        is_full_scan = False
        uses_filesort = False
        uses_temp_table = False

        if explain_plan:
            for row in explain_plan:
                access_type = str(row.get("type", "")).upper()
                extra = str(row.get("Extra", "")).lower()

                if access_type in ["ALL", "INDEX"]:
                    is_full_scan = True
                if "using filesort" in extra:
                    uses_filesort = True
                if "using temporary" in extra:
                    uses_temp_table = True
        else:
            # Heuristic inspection from SQL tokens
            upper_sql = query_sql.upper()
            if "ORDER BY" in upper_sql and "LIMIT" in upper_sql and "WHERE" not in upper_sql:
                uses_filesort = True
            if rows_examined > 10000 and rows_sent < 100:
                is_full_scan = True

        severity = self.classify_bottleneck(
            execution_time_ms=execution_time_ms,
            rows_examined=rows_examined,
            rows_sent=rows_sent,
            is_full_table_scan=is_full_scan,
            uses_filesort=uses_filesort
        )

        return QueryProfileRecord(
            query_sql=query_sql.strip(),
            execution_time_ms=execution_time_ms,
            rows_examined=rows_examined,
            rows_sent=rows_sent,
            is_full_table_scan=is_full_scan,
            uses_filesort=uses_filesort,
            uses_temporary_table=uses_temp_table,
            bottleneck_severity=severity
        )
