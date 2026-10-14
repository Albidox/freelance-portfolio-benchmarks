"""Automated wp_options transient pruner safely purging expired autoloaded options and transients.
Strict zero em dash policy enforced.
"""
import time
from typing import List, Dict, Any, Tuple, Optional
from src.models import TransientPurgeTarget, AutoloadOptionItem
from src.config import WordPressOptimizerConfig


class TransientCleaner:
    """Safely prunes expired WordPress transients and suppresses autoload bloat."""

    def __init__(self, config: Optional[WordPressOptimizerConfig] = None):
        self.config = config or WordPressOptimizerConfig()

    def identify_expired_transients(
        self,
        options: List[Dict[str, Any]],
        current_time: Optional[int] = None
    ) -> List[TransientPurgeTarget]:
        """Scan options dictionary for expired transients and timeout markers."""
        now = int(current_time if current_time is not None else time.time())
        timeouts: Dict[str, int] = {}
        values: Dict[str, int] = {}

        for opt in options:
            name = opt.get("option_name", "")
            val = opt.get("option_value", "")
            size = int(opt.get("option_size_bytes", len(str(val))))

            if name.startswith("_transient_timeout_"):
                key = name.replace("_transient_timeout_", "")
                try:
                    timeouts[key] = int(val)
                except (ValueError, TypeError):
                    timeouts[key] = 0
            elif name.startswith("_site_transient_timeout_"):
                key = name.replace("_site_transient_timeout_", "")
                try:
                    timeouts[key] = int(val)
                except (ValueError, TypeError):
                    timeouts[key] = 0
            elif name.startswith("_transient_"):
                key = name.replace("_transient_", "")
                values[key] = size
            elif name.startswith("_site_transient_"):
                key = name.replace("_site_transient_", "")
                values[key] = size

        purge_targets: List[TransientPurgeTarget] = []

        # Compare timeouts against current timestamp
        for key, timeout_ts in timeouts.items():
            is_expired = timeout_ts < now
            size = values.get(key, 128)
            purge_targets.append(TransientPurgeTarget(
                option_name=f"_transient_{key}",
                option_size_bytes=size,
                is_expired=is_expired,
                timeout_timestamp=timeout_ts,
                purge_reason="expired transient timeout" if is_expired else "active transient"
            ))
            # Also purge the timeout marker itself
            purge_targets.append(TransientPurgeTarget(
                option_name=f"_transient_timeout_{key}",
                option_size_bytes=32,
                is_expired=is_expired,
                timeout_timestamp=timeout_ts,
                purge_reason="expired timeout row" if is_expired else "active timeout row"
            ))

        return purge_targets

    def generate_chunked_purge_sql(self, batch_size: Optional[int] = None) -> List[str]:
        """Generate safe chunked SQL deletion statements with limit clause."""
        batch = batch_size or self.config.batch_purge_limit
        prefix = self.config.table_prefix
        now = int(time.time())
        statements = [
            f"DELETE FROM {prefix}options WHERE option_name LIKE '_transient_timeout_%' AND CAST(option_value AS UNSIGNED) < {now} LIMIT {batch};",
            f"DELETE FROM {prefix}options WHERE option_name LIKE '_site_transient_timeout_%' AND CAST(option_value AS UNSIGNED) < {now} LIMIT {batch};",
            f"DELETE FROM {prefix}options WHERE option_name LIKE '_transient_%' AND option_name NOT LIKE '_transient_timeout_%' AND option_name NOT IN (SELECT CONCAT('_transient_', SUBSTRING(option_name, 20)) FROM (SELECT option_name FROM {prefix}options WHERE option_name LIKE '_transient_timeout_%') AS t) LIMIT {batch};"
        ]
        return statements

    def simulate_purge(self, targets: List[TransientPurgeTarget]) -> Dict[str, Any]:
        """Simulate purge run and calculate reclaimed bytes."""
        expired_count = 0
        reclaimed_bytes = 0
        for target in targets:
            if target.is_expired:
                expired_count += 1
                reclaimed_bytes += target.option_size_bytes

        return {
            "total_inspected": len(targets),
            "expired_count": expired_count,
            "active_count": len(targets) - expired_count,
            "bytes_reclaimed": reclaimed_bytes,
            "kb_reclaimed": round(reclaimed_bytes / 1024.0, 2)
        }
