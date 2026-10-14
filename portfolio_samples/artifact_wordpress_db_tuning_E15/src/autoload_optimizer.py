"""wp_options autoload size aggregator and transient cleaner.
Strict zero em dash policy enforced.
"""
from typing import List, Dict, Any, Tuple, Optional
from src.models import AutoloadOptionItem
from src.config import WordPressOptimizerConfig


class AutoloadOptimizer:
    def __init__(self, config: Optional[WordPressOptimizerConfig] = None):
        self.config = config or WordPressOptimizerConfig()

    def analyze_options(self, options_list: List[Dict[str, Any]]) -> Tuple[float, List[AutoloadOptionItem]]:
        """Analyze autoloaded options, calculate total KB, and recommend optimizations."""
        total_bytes = 0
        analyzed_items: List[AutoloadOptionItem] = []

        for opt in options_list:
            name = opt.get("option_name", "")
            val_bytes = int(opt.get("option_size_bytes", len(str(opt.get("option_value", "")))))
            autoload = opt.get("autoload", "yes")

            if autoload.lower() == "yes":
                total_bytes += val_bytes

            is_transient = name.startswith("_transient_") or name.startswith("_site_transient_")

            # Identify origin plugin or theme heuristics
            plugin_guess = "Core / Unknown"
            if name.startswith("woocommerce_") or name.startswith("wc_"):
                plugin_guess = "WooCommerce"
            elif name.startswith("elementor_"):
                plugin_guess = "Elementor"
            elif name.startswith("yoast_") or name.startswith("wpseo_"):
                plugin_guess = "Yoast SEO"
            elif is_transient:
                plugin_guess = "Transient Cache"

            # Recommendations: large non-critical options should have autoload='no'
            recommended_autoload = autoload
            if is_transient:
                recommended_autoload = "no"
            elif val_bytes > 50000:  # Options larger than 50 KB
                recommended_autoload = "no"

            analyzed_items.append(AutoloadOptionItem(
                option_name=name,
                option_size_bytes=val_bytes,
                is_transient=is_transient,
                current_autoload=autoload,
                recommended_autoload=recommended_autoload,
                plugin_guess=plugin_guess
            ))

        total_kb = round(total_bytes / 1024.0, 2)
        return total_kb, analyzed_items

    def generate_autoload_sql_migrations(self, items: List[AutoloadOptionItem]) -> List[str]:
        """Generate safe SQL statements to set autoload='no' on bloated options."""
        statements = []
        prefix = self.config.table_prefix
        for item in items:
            if item.current_autoload.lower() == "yes" and item.recommended_autoload == "no":
                stmt = f"UPDATE {prefix}options SET autoload = 'no' WHERE option_name = '{item.option_name}';"
                statements.append(stmt)
        return statements

    def generate_transient_purge_sql(self) -> str:
        """Generate query to delete expired transients safely."""
        prefix = self.config.table_prefix
        return f"DELETE FROM {prefix}options WHERE option_name LIKE '_transient_timeout_%' OR option_name LIKE '_site_transient_timeout_%';"
