"""Orphaned metadata detection and safe chunked deletion engine.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional
from src.models import OrphanCleanupSummary, TableType
from src.config import WordPressOptimizerConfig


class OrphanMetaCleaner:
    def __init__(self, config: Optional[WordPressOptimizerConfig] = None):
        self.config = config or WordPressOptimizerConfig()

    def generate_orphan_scan_query(self, child_table: TableType) -> str:
        """Generate diagnostic SELECT query counting orphaned rows."""
        p = self.config.table_prefix
        if child_table == TableType.WP_POSTMETA:
            return f"SELECT COUNT(*) FROM {p}postmeta pm LEFT JOIN {p}posts p ON p.ID = pm.post_id WHERE p.ID IS NULL;"
        elif child_table == TableType.WP_COMMENTMETA:
            return f"SELECT COUNT(*) FROM {p}commentmeta cm LEFT JOIN {p}comments c ON c.comment_ID = cm.comment_id WHERE c.comment_ID IS NULL;"
        return ""

    def generate_chunked_delete_sql(self, child_table: TableType) -> str:
        """Generate safe chunked delete statement preventing lock escalation."""
        p = self.config.table_prefix
        batch = self.config.batch_purge_limit
        if child_table == TableType.WP_POSTMETA:
            return f"DELETE pm FROM {p}postmeta pm LEFT JOIN {p}posts p ON p.ID = pm.post_id WHERE p.ID IS NULL LIMIT {batch};"
        elif child_table == TableType.WP_COMMENTMETA:
            return f"DELETE cm FROM {p}commentmeta cm LEFT JOIN {p}comments c ON c.comment_ID = cm.comment_id WHERE c.comment_ID IS NULL LIMIT {batch};"
        return ""
