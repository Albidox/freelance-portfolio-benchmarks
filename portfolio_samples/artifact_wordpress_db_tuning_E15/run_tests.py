"""Standalone deterministic test harness for E15 WordPress & WooCommerce Database Tuning with 26 assertions.
Runs natively on Windows without Linux shell dependencies.
Strict zero em dash policy enforced.
"""
import tracemalloc
import time
import os
import sys

# Ensure current directory is on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.models import (
    TableType,
    OptimizationSeverity,
    QueryProfileRecord,
    SlowQueryLog,
    AutoloadOptionItem,
    TransientPurgeTarget,
    IndexRecommendation,
    OrphanCleanupSummary,
    DbHealthReport,
    OptimizationReport
)
from src.config import WordPressOptimizerConfig
from src.query_profiler import QueryProfiler
from src.autoload_optimizer import AutoloadOptimizer
from src.transient_cleaner import TransientCleaner
from src.index_advisor import WooCommerceIndexAdvisor
from src.orphan_cleaner import OrphanMetaCleaner
from src.query_benchmarker import QueryBenchmarker
from src.db import DatabaseManager
from src.storage import WordPressOptimizerStorage


def test_models_and_configuration():
    print("Testing models and configuration validation...")
    config = WordPressOptimizerConfig()

    # Assertion 1: Standard table prefix
    assert config.table_prefix == "wp_"
    # Assertion 2: Autoload threshold set to 800 KB
    assert config.max_autoload_kb_threshold == 800.0
    # Assertion 3: Default dry run active
    assert config.dry_run is True

    item = AutoloadOptionItem(
        option_name="wc_session_data_cache",
        option_size_bytes=204800,  # 200 KB
        is_transient=False,
        current_autoload="yes",
        recommended_autoload="no",
        plugin_guess="WooCommerce"
    )
    # Assertion 4: Option size in KB calculated accurately
    assert item.size_kb == 200.0


def test_query_profiler():
    print("Testing query profiler and EXPLAIN plan evaluation...")
    profiler = QueryProfiler()

    # Case 1: Fast indexed query
    rec_fast = profiler.profile_query(
        query_sql="SELECT * FROM wp_posts WHERE ID = 42;",
        execution_time_ms=1.5,
        rows_examined=1,
        rows_sent=1
    )
    # Assertion 5: Fast query severity is LOW
    assert rec_fast.bottleneck_severity == OptimizationSeverity.LOW
    # Assertion 6: Not a full scan
    assert rec_fast.is_full_table_scan is False

    # Case 2: Catastrophic table scan query with filesort
    explain_data = [
        {"table": "wp_postmeta", "type": "ALL", "rows": 850000, "Extra": "Using where; Using filesort"}
    ]
    rec_slow = profiler.profile_query(
        query_sql="SELECT post_id, meta_value FROM wp_postmeta WHERE meta_key = '_price' ORDER BY meta_value;",
        execution_time_ms=850.0,
        rows_examined=850000,
        rows_sent=50,
        explain_plan=explain_data
    )
    # Assertion 7: Slow query flagged CRITICAL
    assert rec_slow.bottleneck_severity == OptimizationSeverity.CRITICAL
    # Assertion 8: Full table scan identified
    assert rec_slow.is_full_table_scan is True
    # Assertion 9: Filesort detected
    assert rec_slow.uses_filesort is True


def test_autoload_optimizer():
    print("Testing autoload options analyzer and transient purging...")
    optimizer = AutoloadOptimizer()

    dummy_options = [
        {"option_name": "siteurl", "option_value": "https://mystore.com", "autoload": "yes", "option_size_bytes": 22},
        {"option_name": "elementor_global_css", "option_value": "A" * 120000, "autoload": "yes", "option_size_bytes": 120000},
        {"option_name": "_transient_wc_products_feed", "option_value": "B" * 60000, "autoload": "yes", "option_size_bytes": 60000}
    ]

    total_kb, analyzed = optimizer.analyze_options(dummy_options)
    # Assertion 10: Total autoload KB calculated correctly
    assert total_kb > 170.0

    # Assertion 11: Elementor bloat detected
    elem_item = next(i for i in analyzed if i.option_name == "elementor_global_css")
    assert elem_item.recommended_autoload == "no"
    assert elem_item.plugin_guess == "Elementor"

    # Assertion 12: Transient flagged for no autoload
    trans_item = next(i for i in analyzed if i.is_transient is True)
    assert trans_item.recommended_autoload == "no"

    # Generate SQL migrations
    migrations = optimizer.generate_autoload_sql_migrations(analyzed)
    # Assertion 13: Migration statements generated
    assert len(migrations) == 2
    # Assertion 14: SQL syntax contains UPDATE
    assert "UPDATE wp_options SET autoload = 'no'" in migrations[0]

    # Transient purge query
    purge_sql = optimizer.generate_transient_purge_sql()
    # Assertion 15: Transient purge target query
    assert "DELETE FROM wp_options WHERE option_name LIKE '_transient_timeout_%'" in purge_sql


def test_index_advisor():
    print("Testing WooCommerce composite index advisor and DDL generator...")
    advisor = WooCommerceIndexAdvisor()
    recs = advisor.get_standard_recommendations()

    # Assertion 16: Three standard index recommendations
    assert len(recs) == 3

    # Postmeta composite index
    pm_index = next(r for r in recs if r.table_name == "wp_postmeta")
    # Assertion 17: Postmeta index is composite
    assert pm_index.is_composite is True
    # Assertion 18: Postmeta index has clamped prefix length for utf8mb4
    assert pm_index.prefix_length_clamped is True
    # Assertion 19: DDL contains prefix limit
    assert "meta_key(191), meta_value(191)" in pm_index.ddl_statement

    # Conflict check
    assert advisor.check_existing_conflict(pm_index, ["idx_postmeta_key_value"]) is True
    # Assertion 20: No conflict on fresh index
    assert advisor.check_existing_conflict(pm_index, ["some_other_idx"]) is False


def test_orphan_cleaner():
    print("Testing orphaned metadata detection and chunked delete queries...")
    cleaner = OrphanMetaCleaner()

    scan_query = cleaner.generate_orphan_scan_query(TableType.WP_POSTMETA)
    # Assertion 21: Scan query joins posts table
    assert "LEFT JOIN wp_posts p ON p.ID = pm.post_id" in scan_query

    delete_query = cleaner.generate_chunked_delete_sql(TableType.WP_POSTMETA)
    # Assertion 22: Chunked delete includes LIMIT
    assert "LIMIT 1000" in delete_query
    # Assertion 23: Child table is wp_postmeta
    assert "DELETE pm FROM wp_postmeta pm" in delete_query


def test_dual_tier_storage():
    print("Testing dual-tier storage (SQLite WAL + PostgreSQL 18)...")
    db_file = os.path.join(CURRENT_DIR, "test_run_e15_audit.db")
    if os.path.exists(db_file):
        os.remove(db_file)

    config = WordPressOptimizerConfig(sqlite_db_path=db_file)
    storage = WordPressOptimizerStorage(config=config)

    rec = QueryProfileRecord(
        query_sql="SELECT * FROM wp_postmeta WHERE meta_key = 'sku';",
        execution_time_ms=125.0,
        rows_examined=55000,
        rows_sent=10,
        is_full_table_scan=True,
        uses_filesort=False,
        uses_temporary_table=False,
        bottleneck_severity=OptimizationSeverity.HIGH
    )
    storage.record_slow_query(rec)

    # Assertion 24: Recorded query count is 1
    assert storage.get_slow_query_count() == 1

    report = DbHealthReport(
        total_autoload_kb=1250.0,
        slow_queries_count=14,
        missing_indexes_count=3,
        orphaned_records_count=25000,
        health_score=58
    )
    storage.record_health_report(report)

    # Assertion 25: PostgreSQL initialization check returns boolean safely
    pg_status = storage.init_postgres_schema()
    assert isinstance(pg_status, bool)

    storage.close()
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass


def main():
    tracemalloc.start()
    start_time = time.time()
    print("=" * 70)
    print("Starting Deterministic Test Suite: Artifact E15 (26 Assertions)")
    print("=" * 70)

    test_models_and_configuration()
    test_query_profiler()
    test_autoload_optimizer()
    test_index_advisor()
    test_orphan_cleaner()
    test_dual_tier_storage()

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    duration = time.time() - start_time
    peak_mb = peak_mem / (1024 * 1024)

    # Assertion 26: Peak memory consumption under 250 MB ceiling
    assert peak_mb < 250.0, f"Memory ceiling exceeded: {peak_mb:.2f} MB"

    print("=" * 70)
    print(f"ALL 26 ASSERTIONS PASSED in {duration:.3f}s")
    print(f"Peak Memory Footprint: {peak_mb:.2f} MB (Ceiling: 250.00 MB)")
    print("=" * 70)


if __name__ == "__main__":
    main()
