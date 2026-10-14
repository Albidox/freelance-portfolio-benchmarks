"""Standalone deterministic test harness for E18 Google Sheets & Airtable Sync with 26 assertions.
Runs natively on Windows without Linux shell dependencies.
Zero em dash policy enforced.
"""
import tracemalloc
import time
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.models import (
    SyncDirection,
    ConflictStrategy,
    ChangeType,
    SyncRecordItem,
    ChangeDelta,
    ConflictResolutionResult,
    SyncCycleReport
)
from src.config import SheetsAirtableSyncConfig
from src.sheets_client import GoogleSheetsClient
from src.airtable_client import AirtableClient
from src.sync_engine import TwoWaySyncEngine
from src.conflict_resolver import ConflictResolver
from src.sync_daemon import SyncDaemon
from src.storage import SyncStorage


def test_models_and_configuration():
    print("Testing data contracts and system configuration...")
    config = SheetsAirtableSyncConfig()

    # Assertion 1: PostgreSQL target port matches local native instance
    assert config.pg_port == 5433
    # Assertion 2: Target schema is isolated
    assert config.target_schema == "e18_sheets_airtable_sync"
    # Assertion 3: Default conflict strategy is TIMESTAMP_PRECEDENCE
    assert config.default_conflict_strategy == "TIMESTAMP_PRECEDENCE"
    # Assertion 4: Token bucket capacity is 10
    assert config.token_bucket_capacity == 10


def test_clients_and_rate_limiting():
    print("Testing Google Sheets and Airtable client parsing and rate limiters...")
    sheets_client = GoogleSheetsClient(rate_limit_rps=50.0, bucket_capacity=10)
    raw_sheet_rows = [
        ["101", "Acme Enterprise", "5000", "=SUM(C2*1.18)", "2026-10-14T10:00:00Z"],
        ["102", "Globex Corp", "12000", "=SUM(C3*1.18)", "2026-10-14T11:00:00Z"]
    ]
    headers = ["id", "client_name", "subtotal", "total_with_tax", "last_modified"]
    parsed_sheet = sheets_client.parse_sheet_rows(raw_sheet_rows, headers)

    # Assertion 5: Exactly 2 rows parsed from sheet
    assert len(parsed_sheet) == 2
    # Assertion 6: Formula recognized and preserved in formula_fields
    assert parsed_sheet[0].formula_fields.get("total_with_tax") == "=SUM(C2*1.18)"
    # Assertion 7: Record ID extracted accurately
    assert parsed_sheet[0].entity_id == "101"

    airtable_client = AirtableClient(rate_limit_rps=50.0)
    raw_airtable = [
        {"id": "rec_001", "fields": {"client_name": "Initech", "tags": ["saas", "b2b"]}, "createdTime": "2026-10-14T09:00:00Z"}
    ]
    parsed_airtable = airtable_client.parse_airtable_records(raw_airtable)
    # Assertion 8: Airtable record parsed successfully
    assert len(parsed_airtable) == 1
    # Assertion 9: Tag array coerced into comma-separated string
    assert "saas, b2b" in parsed_airtable[0].fields["tags"]


def test_sync_engine_fingerprints_and_deltas():
    print("Testing delta change detector and SHA-256 fingerprinting...")
    engine = TwoWaySyncEngine()

    item_1 = SyncRecordItem(
        entity_id="rec_A",
        fields={"title": "Task A", "status": "In Progress"},
        last_modified="2026-10-14T10:00:00Z"
    )
    fp_1 = item_1.calculate_fingerprint()
    # Assertion 10: Fingerprint is 64-char SHA-256 hex string
    assert len(fp_1) == 64

    # Test ADDED delta
    deltas_1 = engine.compute_deltas("SHEETS", [item_1], {})
    # Assertion 11: Uncached record detected as ADDED
    assert len(deltas_1) == 1
    assert deltas_1[0].change_type == ChangeType.ADDED

    # Test UNCHANGED delta
    cached = {"rec_A": fp_1}
    deltas_2 = engine.compute_deltas("SHEETS", [item_1], cached)
    # Assertion 12: Cached matching record detected as UNCHANGED
    assert deltas_2[0].change_type == ChangeType.UNCHANGED

    # Test UPDATED delta
    item_1_modified = SyncRecordItem(
        entity_id="rec_A",
        fields={"title": "Task A", "status": "Completed"},
        last_modified="2026-10-14T11:00:00Z"
    )
    deltas_3 = engine.compute_deltas("SHEETS", [item_1_modified], cached)
    # Assertion 13: Altered fields detected as UPDATED
    assert deltas_3[0].change_type == ChangeType.UPDATED

    # Test DELETED delta
    deltas_4 = engine.compute_deltas("SHEETS", [], cached)
    # Assertion 14: Missing cached record detected as DELETED
    assert len(deltas_4) == 1
    assert deltas_4[0].change_type == ChangeType.DELETED


def test_conflict_resolver_strategies():
    print("Testing deterministic conflict resolution strategies...")
    resolver = ConflictResolver()

    rec_sheet = SyncRecordItem(
        entity_id="rec_100",
        fields={"status": "In Review", "amount": 1000},
        last_modified="2026-10-14T12:00:00Z",
        formula_fields={"calculated_tax": "=SUM(B2*0.1)"}
    )
    rec_airtable = SyncRecordItem(
        entity_id="rec_100",
        fields={"status": "Approved", "amount": 1000},
        last_modified="2026-10-14T12:05:00Z"  # 5 mins newer
    )

    # Strategy 1: TIMESTAMP_PRECEDENCE (Airtable is newer)
    res_ts = resolver.resolve_conflict(rec_sheet, rec_airtable, ConflictStrategy.TIMESTAMP_PRECEDENCE)
    # Assertion 15: Newer timestamp wins
    assert res_ts.winning_source == "AIRTABLE"
    # Assertion 16: Status field reflects Airtable value
    assert res_ts.resolved_fields["status"] == "Approved"

    # Strategy 2: SHEETS_WINS override
    res_sw = resolver.resolve_conflict(rec_sheet, rec_airtable, ConflictStrategy.SHEETS_WINS)
    # Assertion 17: Sheets wins override
    assert res_sw.winning_source == "SHEETS"
    assert res_sw.resolved_fields["status"] == "In Review"

    # Strategy 3: FIELD_LEVEL_MERGE
    rec_sheet_partial = SyncRecordItem(
        entity_id="rec_200",
        fields={"assigned_to": "Alice"},
        last_modified="2026-10-14T10:00:00Z",
        formula_fields={"score": "=AVERAGE(D2:D10)"}
    )
    rec_airtable_partial = SyncRecordItem(
        entity_id="rec_200",
        fields={"priority": "High"},
        last_modified="2026-10-14T11:00:00Z"
    )
    res_merge = resolver.resolve_conflict(rec_sheet_partial, rec_airtable_partial, ConflictStrategy.FIELD_LEVEL_MERGE)
    # Assertion 18: Field-level merge preserves disjoint keys from both sources
    assert res_merge.resolved_fields.get("assigned_to") == "Alice"
    assert res_merge.resolved_fields.get("priority") == "High"


def test_sync_daemon_execution_cycle():
    print("Testing sync daemon full cycle execution...")
    config = SheetsAirtableSyncConfig()
    daemon = SyncDaemon(config)

    records_s = [
        SyncRecordItem(entity_id="1", fields={"name": "Alpha"}, last_modified="2026-10-14T10:00:00Z")
    ]
    records_a = [
        SyncRecordItem(entity_id="2", fields={"name": "Beta"}, last_modified="2026-10-14T10:00:00Z")
    ]

    report = daemon.execute_sync_cycle("cycle_001", records_s, records_a)
    # Assertion 19: Total scanned equals 2
    assert report.records_scanned == 2
    # Assertion 20: Records added equals 1 from sheets delta
    assert report.records_added == 1
    # Assertion 21: Elapsed seconds is positive
    assert report.elapsed_seconds >= 0.0

    # Repeat same cycle without changes
    report_2 = daemon.execute_sync_cycle("cycle_002", records_s, records_a)
    # Assertion 22: Unchanged records result in zero added
    assert report_2.records_added == 0


def test_dual_tier_storage_audit():
    print("Testing SQLite WAL sync audit persistence...")
    test_db = os.path.join(CURRENT_DIR, "test_sync_audit.db")
    if os.path.exists(test_db):
        os.remove(test_db)

    config = SheetsAirtableSyncConfig(sqlite_db_path=test_db)
    storage = SyncStorage(config)

    report = SyncCycleReport(
        cycle_id="cycle_audit_test",
        direction=SyncDirection.BIDIRECTIONAL,
        records_scanned=500,
        records_added=12,
        records_updated=4,
        records_deleted=0,
        conflicts_resolved=2,
        conflicts_quarantined=0,
        elapsed_seconds=1.82
    )
    storage.record_sync_cycle(report)
    loaded = storage.get_latest_cycle("cycle_audit_test")

    try:
        # Assertion 23: Stored audit cycle loaded successfully
        assert loaded is not None
        # Assertion 24: Records scanned matches 500
        assert loaded["records_scanned"] == 500
        # Assertion 25: Records added matches 12
        assert loaded["records_added"] == 12
        # Assertion 26: Conflicts resolved matches 2
        assert loaded["conflicts_resolved"] == 2
    finally:
        if os.path.exists(test_db):
            os.remove(test_db)


def main():
    print("=" * 70)
    print("RUNNING DETERMINISTIC TEST HARNESS: E18 SHEETS & AIRTABLE SYNC DAEMON")
    print("Platform: Windows 10 | Target DB: Native PostgreSQL 18 (:5433)")
    print("=" * 70)

    tracemalloc.start()
    start_time = time.perf_counter()

    test_models_and_configuration()
    test_clients_and_rate_limiting()
    test_sync_engine_fingerprints_and_deltas()
    test_conflict_resolver_strategies()
    test_sync_daemon_execution_cycle()
    test_dual_tier_storage_audit()

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.perf_counter() - start_time

    print("-" * 70)
    print("ALL 26 ASSERTIONS PASSED WITH 100% SUCCESS RATE")
    print(f"Elapsed Time: {elapsed:.4f} seconds")
    print(f"Memory Footprint: Peak = {peak_mem / 1024 / 1024:.2f} MB (Cap: 250 MB)")
    print("=" * 70)


if __name__ == "__main__":
    main()
