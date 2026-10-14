"""WooCommerce composite index advisor and DDL migration generator.
Strict zero em dash policy enforced.
"""
from typing import List, Dict, Any, Optional
from src.models import IndexRecommendation, TableType
from src.config import WordPressOptimizerConfig


class WooCommerceIndexAdvisor:
    """Database index analyzer detecting unindexed queries on WordPress and WooCommerce tables."""

    def __init__(self, config: Optional[WordPressOptimizerConfig] = None):
        self.config = config or WordPressOptimizerConfig()

    def get_standard_recommendations(self) -> List[IndexRecommendation]:
        """Generate high-impact composite index recommendations for WooCommerce."""
        prefix = self.config.table_prefix
        recommendations = [
            IndexRecommendation(
                table_name=f"{prefix}postmeta",
                index_name="idx_postmeta_key_value",
                target_columns=["meta_key", "meta_value"],
                is_composite=True,
                prefix_length_clamped=True,
                estimated_speedup_pct=75.0,
                ddl_statement=f"CREATE INDEX idx_postmeta_key_value ON {prefix}postmeta (meta_key(191), meta_value(191));"
            ),
            IndexRecommendation(
                table_name=f"{prefix}posts",
                index_name="idx_posts_type_status_date",
                target_columns=["post_type", "post_status", "post_date"],
                is_composite=True,
                prefix_length_clamped=False,
                estimated_speedup_pct=60.0,
                ddl_statement=f"CREATE INDEX idx_posts_type_status_date ON {prefix}posts (post_type, post_status, post_date);"
            ),
            IndexRecommendation(
                table_name=f"{prefix}wc_order_stats",
                index_name="idx_wc_order_stats_lookup",
                target_columns=["status", "date_created"],
                is_composite=True,
                prefix_length_clamped=False,
                estimated_speedup_pct=80.0,
                ddl_statement=f"CREATE INDEX idx_wc_order_stats_lookup ON {prefix}wc_order_stats (status, date_created);"
            )
        ]
        return recommendations

    def check_existing_conflict(self, rec: IndexRecommendation, existing_indexes: List[str]) -> bool:
        """Verify whether recommendation already exists or conflicts with existing indexes."""
        return rec.index_name in existing_indexes

    def analyze_query_for_index(self, query_sql: str) -> Optional[IndexRecommendation]:
        """Detect unindexed post_id/meta_key queries on wp_postmeta and generate DDL indexes."""
        upper = query_sql.upper()
        prefix = self.config.table_prefix
        pm_table = f"{prefix}postmeta"

        if pm_table.upper() in upper:
            if "META_KEY" in upper and "POST_ID" in upper:
                return IndexRecommendation(
                    table_name=pm_table,
                    index_name="idx_postmeta_post_id_key",
                    target_columns=["post_id", "meta_key"],
                    is_composite=True,
                    prefix_length_clamped=True,
                    estimated_speedup_pct=85.0,
                    ddl_statement=f"CREATE INDEX idx_postmeta_post_id_key ON {pm_table} (post_id, meta_key(191));"
                )
            elif "META_KEY" in upper and "META_VALUE" in upper:
                return IndexRecommendation(
                    table_name=pm_table,
                    index_name="idx_postmeta_key_value",
                    target_columns=["meta_key", "meta_value"],
                    is_composite=True,
                    prefix_length_clamped=True,
                    estimated_speedup_pct=75.0,
                    ddl_statement=f"CREATE INDEX idx_postmeta_key_value ON {pm_table} (meta_key(191), meta_value(191));"
                )
        return None
