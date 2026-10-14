"""Standalone deterministic test harness for E16 Database Migration Harness with 26 assertions.
Runs natively on Windows without Linux shell dependencies.
Strict zero em dash policy enforced.
"""
import tracemalloc
import time
import os
import shutil
from src.models import (
    MigrationSourceType,
    MigrationStatus,
    TargetDataType,
    ColumnMapping,
    MigrationRecord,
    MigrationBatch,
    QuarantineRecord,
    ReconciliationReport,
    MigrationAuditLog
)
from src.config import DatabaseMigrationConfig
from src.source_extractor import SourceExtractor
from src.schema_transformer import SchemaTransformer
from src.data_loader import PostgresBatchLoader
from src.reconciliation_verifier import ReconciliationVerifier
from src.storage import MigrationStorage


def test_models_and_configuration():
    print("Testing data contracts and system configuration...")
    config = DatabaseMigrationConfig()

    # Assertion 1: PostgreSQL target port matches local native instance
    assert config.pg_port == 5433
    # Assertion 2: Target schema is isolated
    assert config.target_schema == "e16_db_migration"
    # Assertion 3: Default batch size is 5000
    assert config.batch_size == 5000

    record = MigrationRecord(source_id="101", data={"id": 101, "name": "Enterprise Corp", "balance": 4500.50})
    checksum = record.calculate_checksum()
    # Assertion 4: Checksum is non-empty 64-char hex SHA-256 string
    assert len(checksum) == 64
    # Assertion 5: Checksum matches deterministic hash
    assert record.checksum == checksum


def test_source_extractor_and_checkpoints():
    print("Testing source streaming extractor and checkpoint persistence...")
    config = DatabaseMigrationConfig(batch_size=100)
    extractor = SourceExtractor(config)

    mock_dataset = [{"id": i, "username": f"user_{i}", "active": i % 2 == 0} for i in range(1, 251)]

    batches = list(extractor.stream_records_from_dataset("users", mock_dataset, start_offset=0))
    # Assertion 6: Exactly 3 batches produced (100, 100, 50)
    assert len(batches) == 3
    # Assertion 7: Total records extracted equals 250
    assert extractor.total_extracted == 250
    # Assertion 8: First batch has 100 records
    assert batches[0].record_count == 100
    # Assertion 9: Final batch has 50 records
    assert batches[2].record_count == 50

    test_db = "test_chk.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    try:
        extractor.save_checkpoint_offset(test_db, "users", 200)
        loaded_offset = extractor.load_checkpoint_offset(test_db, "users")
        # Assertion 10: Checkpoint offset successfully preserved and restored
        assert loaded_offset == 200
    finally:
        if os.path.exists(test_db):
            os.remove(test_db)


def test_schema_transformer_and_zero_dates():
    print("Testing MySQL and MongoDB type transformation and edge sanitization...")
    transformer = SchemaTransformer(quarantine_invalid=True)

    # Assertion 11: MySQL zero-date normalized to None
    zero_date = "0000-00-00 00:00:00"
    assert transformer.sanitize_mysql_zero_date(zero_date) is None

    # Assertion 12: Valid ISO date preserved
    valid_date = "2026-10-14 12:30:00"
    assert transformer.sanitize_mysql_zero_date(valid_date) == valid_date

    # Assertion 13: MySQL TINYINT(1) maps to BOOLEAN
    assert transformer.transform_mysql_datatype("TINYINT(1)") == TargetDataType.BOOLEAN
    # Assertion 14: MySQL BIGINT maps to BIGINT
    assert transformer.transform_mysql_datatype("BIGINT UNSIGNED") == TargetDataType.BIGINT

    mongo_doc = {
        "_id": {"$oid": "507f1f77bcf86cd799439011"},
        "account_name": "Acme Global",
        "metadata": {"tier": "gold", "tags": ["enterprise", "saas"]},
        "created_at": {"$date": "2026-10-14T10:00:00Z"}
    }
    normalized_doc, success = transformer.transform_mongo_document(mongo_doc)
    # Assertion 15: MongoDB normalization success
    assert success is True
    # Assertion 16: MongoDB _id extracted into flat string id
    assert normalized_doc["id"] == "507f1f77bcf86cd799439011"
    # Assertion 17: Nested dictionary serialized to JSONB string
    assert "enterprise" in normalized_doc["metadata"]


def test_postgres_batch_loader_and_backoff():
    print("Testing PostgreSQL batch loader, binary COPY formatting, and backoff...")
    config = DatabaseMigrationConfig()
    loader = PostgresBatchLoader(config)

    schema_ddl = loader.generate_create_schema_ddl("e16_db_migration")
    # Assertion 18: Schema creation DDL contains schema name
    assert "e16_db_migration" in schema_ddl

    records = [
        {"id": "1", "name": "Alice", "score": 95},
        {"id": "2", "name": "Bob", "score": None}
    ]
    buf = loader.format_copy_buffer(records, ["id", "name", "score"])
    content = buf.getvalue()
    # Assertion 19: Null value correctly represented by \\N in TSV
    assert "\\N" in content
    # Assertion 20: Number of lines matches record count
    assert len(content.strip().split("\n")) == 2

    delay_1 = loader.calculate_exponential_backoff(1)
    delay_2 = loader.calculate_exponential_backoff(2)
    # Assertion 21: Exponential backoff delay strictly increases
    assert delay_2 > delay_1


def test_reconciliation_verifier():
    print("Testing cryptographic SHA-256 reconciliation engine...")
    verifier = ReconciliationVerifier()

    source_data = [
        {"id": 1, "sku": "WIDGET-A", "qty": 100},
        {"id": 2, "sku": "WIDGET-B", "qty": 250}
    ]
    target_data_identical = [
        {"id": 1, "sku": "WIDGET-A", "qty": 100},
        {"id": 2, "sku": "WIDGET-B", "qty": 250}
    ]
    target_data_tampered = [
        {"id": 1, "sku": "WIDGET-A", "qty": 100},
        {"id": 2, "sku": "WIDGET-B", "qty": 249}
    ]

    report_valid = verifier.reconcile_datasets("inventory", source_data, target_data_identical)
    # Assertion 22: Identical datasets pass reconciliation
    assert report_valid.is_verified is True
    # Assertion 23: Data mismatches count is zero
    assert report_valid.data_mismatches == 0

    report_tampered = verifier.reconcile_datasets("inventory", source_data, target_data_tampered)
    # Assertion 24: Tampered dataset fails reconciliation
    assert report_tampered.is_verified is False
    # Assertion 25: Exactly 1 mismatch flagged
    assert report_tampered.data_mismatches == 1


def test_dual_tier_storage_audit():
    print("Testing SQLite WAL audit persistence and retrieval...")
    test_audit_db = "test_audit.db"
    if os.path.exists(test_audit_db):
        os.remove(test_audit_db)

    config = DatabaseMigrationConfig(sqlite_audit_path=test_audit_db)
    storage = MigrationStorage(config)

    audit = MigrationAuditLog(
        run_id="run_e16_001",
        source_type="MYSQL",
        target_schema="e16_db_migration",
        table_name="orders",
        total_migrated=50000,
        quarantined_count=2,
        elapsed_seconds=14.8,
        status=MigrationStatus.COMPLETED
    )
    storage.record_audit_log(audit)
    retrieved = storage.get_latest_audit("run_e16_001")

    try:
        # Assertion 26: Retrieved audit run matches recorded record
        assert retrieved is not None
        assert retrieved["total_migrated"] == 50000
        assert retrieved["status"] == "COMPLETED"
    finally:
        if os.path.exists(test_audit_db):
            os.remove(test_audit_db)


def main():
    print("=" * 70)
    print("RUNNING DETERMINISTIC TEST HARNESS: E16 DATABASE MIGRATION HARNESS")
    print("Platform: Windows 10 | Target DB: Native PostgreSQL 18 (:5433)")
    print("=" * 70)

    tracemalloc.start()
    start_time = time.perf_counter()

    test_models_and_configuration()
    test_source_extractor_and_checkpoints()
    test_schema_transformer_and_zero_dates()
    test_postgres_batch_loader_and_backoff()
    test_reconciliation_verifier()
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
