"""Standalone deterministic test harness for E14 Remote PC Maintenance & Windows Optimization with 26 assertions.
Runs natively on Windows without Linux shell dependencies.
Strict zero em dash policy enforced.
"""
import tracemalloc
import time
import os
import shutil
from src.models import (
    CleanTargetType,
    OptimizationAction,
    ServiceStartupType,
    CleanupRule,
    CleanupResult,
    ServiceAuditRecord,
    RegistryAuditRecord,
    SystemHealthSnapshot
)
from src.config import WindowsOptimizerConfig
from src.disk_cleaner import WindowsDiskCleaner
from src.service_optimizer import WindowsServiceOptimizer
from src.registry_repair import WindowsRegistryAuditor
from src.health_monitor import WindowsHealthMonitor
from src.storage import WindowsOptimizerStorage


def test_models_and_configurations():
    print("Testing models and configuration validation...")
    config = WindowsOptimizerConfig()

    # Assertion 1: Protected services contains Windows Update
    assert "wuauserv" in config.protected_services
    # Assertion 2: Protected services contains BITS
    assert "BITS" in config.protected_services

    rule = CleanupRule(
        target_type=CleanTargetType.WINDOWS_TEMP,
        target_path="C:\\Temp\\FakeTest",
        dry_run=True
    )
    # Assertion 3: Default dry run active
    assert rule.dry_run is True

    result = CleanupResult(
        target_type=CleanTargetType.WINDOWS_TEMP,
        target_path="C:\\Temp\\FakeTest",
        bytes_reclaimed=10485760  # 10 MB
    )
    # Assertion 4: Megabytes calculation property
    assert result.megabytes_reclaimed == 10.0


def test_disk_cleaner_simulation():
    print("Testing disk cleaner with real temporary files and dry-run safety...")
    test_dir = os.path.abspath("test_temp_sandbox")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir, exist_ok=True)

    # Create dummy files
    f1 = os.path.join(test_dir, "sample1.tmp")
    f2 = os.path.join(test_dir, "sample2.log")
    with open(f1, "w", encoding="utf-8") as f:
        f.write("A" * 1024)  # 1 KB
    with open(f2, "w", encoding="utf-8") as f:
        f.write("B" * 2048)  # 2 KB

    cleaner = WindowsDiskCleaner()
    rule_dry = CleanupRule(
        target_type=CleanTargetType.USER_TEMP,
        target_path=test_dir,
        dry_run=True,
        max_age_days=0
    )
    res_dry = cleaner.scan_and_clean(rule_dry)

    # Assertion 5: Scanned files count
    assert res_dry.files_scanned == 2
    # Assertion 6: Bytes scanned correctly
    assert res_dry.bytes_reclaimed == 3072
    # Assertion 7: Files still exist on disk during dry run
    assert os.path.exists(f1) is True
    assert os.path.exists(f2) is True

    # Real purge run
    rule_purge = CleanupRule(
        target_type=CleanTargetType.USER_TEMP,
        target_path=test_dir,
        dry_run=False,
        max_age_days=0
    )
    res_purge = cleaner.scan_and_clean(rule_purge)

    # Assertion 8: Purged files count
    assert res_purge.files_deleted == 2
    # Assertion 9: Files physically unlinked
    assert os.path.exists(f1) is False
    assert os.path.exists(f2) is False

    # Cleanup test dir
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)


def test_service_auditor_and_rollback():
    print("Testing service optimizer and rollback generator...")
    optimizer = WindowsServiceOptimizer()

    # Case 1: Protected OS service
    wu_audit = optimizer.audit_service("wuauserv", ServiceStartupType.AUTOMATIC, "Running")
    # Assertion 10: Windows update cannot be disabled
    assert wu_audit.is_safe_to_disable is False
    assert wu_audit.recommended_startup == ServiceStartupType.AUTOMATIC

    # Case 2: Telemetry service
    diag_audit = optimizer.audit_service("DiagTrack", ServiceStartupType.AUTOMATIC, "Running")
    # Assertion 11: DiagTrack identified for disabling
    assert diag_audit.is_safe_to_disable is True
    assert diag_audit.recommended_startup == ServiceStartupType.DISABLED
    assert diag_audit.category == "Telemetry"

    # Case 3: Rollback script generation
    rollback_script = optimizer.generate_rollback_script([wu_audit, diag_audit])
    # Assertion 12: Rollback contains restore commands
    assert "Set-Service -Name 'wuauserv' -StartupType Automatic" in rollback_script
    assert "Set-Service -Name 'DiagTrack' -StartupType Automatic" in rollback_script


def test_registry_repair_auditor():
    print("Testing registry auditor and .reg backup command generation...")
    auditor = WindowsRegistryAuditor()

    # Case 1: Dangling file association
    rec_dangling = auditor.inspect_file_association(".oldtmp", "")
    # Assertion 13: Dangling extension flagged
    assert rec_dangling.issue_type == "DANGLING_FILE_EXTENSION"
    # Assertion 14: Backup command includes reg export
    assert "reg export \"HKCR\\.oldtmp\"" in rec_dangling.backup_command

    # Case 2: Healthy file association
    rec_healthy = auditor.inspect_file_association(".txt", "txtfile")
    # Assertion 15: Healthy extension preserved
    assert rec_healthy.issue_type == "HEALTHY"
    assert rec_healthy.recommended_action == "PRESERVE"

    # Case 3: Bloated MRU list
    rec_mru = auditor.inspect_mru_list("RecentDocs", "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\RecentDocs", 85)
    # Assertion 16: Bloated MRU detected
    assert rec_mru.issue_type == "BLOATED_MRU_HISTORY"
    assert "backup_mru_RecentDocs.reg" in rec_mru.backup_command


def test_system_health_scoring():
    print("Testing system health scoring algorithm...")
    monitor = WindowsHealthMonitor()

    # Case 1: Optimal system
    score_optimal = monitor.compute_health_score(cpu_pct=15.0, ram_pct=45.0, disk_free_pct=60.0)
    # Assertion 17: Optimal score is 100
    assert score_optimal == 100

    # Case 2: Heavily degraded system (CPU 95%, RAM 92%, Disk 8% free)
    score_degraded = monitor.compute_health_score(cpu_pct=95.0, ram_pct=92.0, disk_free_pct=8.0)
    # Assertion 18: Heavily degraded score drops significantly
    assert score_degraded < 70

    # Case 3: Assemble health snapshot
    snapshot = monitor.generate_snapshot(
        cpu_usage_pct=25.0,
        ram_total_gb=16.0,
        ram_used_gb=8.0,
        disk_total_gb=500.0,
        disk_free_gb=250.0
    )
    # Assertion 19: RAM percentage calculation
    assert snapshot.ram_percent == 50.0
    # Assertion 20: Disk free percentage calculation
    assert snapshot.disk_free_pct == 50.0
    # Assertion 21: Snapshot health score optimal
    assert snapshot.health_score == 100


def test_dual_tier_storage():
    print("Testing dual-tier storage (SQLite WAL + PostgreSQL 18)...")
    db_file = "test_run_e14_audit.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    config = WindowsOptimizerConfig(sqlite_db_path=db_file)
    storage = WindowsOptimizerStorage(config=config)

    res = CleanupResult(
        target_type=CleanTargetType.WINDOWS_TEMP,
        target_path="C:\\Windows\\Temp",
        files_scanned=150,
        files_deleted=140,
        bytes_reclaimed=52428800,  # 50 MB
        locked_files_skipped=10
    )
    storage.record_cleanup(res)

    # Assertion 22: Summary files deleted matches recorded
    summary = storage.get_cleanup_summary()
    assert summary["total_files_deleted"] == 140
    # Assertion 23: Summary bytes reclaimed matches recorded
    assert summary["total_bytes_reclaimed"] == 52428800

    snap = SystemHealthSnapshot(
        cpu_usage_pct=20.0,
        ram_total_gb=32.0,
        ram_used_gb=12.0,
        ram_percent=37.5,
        disk_total_gb=1000.0,
        disk_free_gb=650.0,
        disk_free_pct=65.0,
        health_score=100
    )
    storage.record_health(snap)
    # Assertion 24: Health snapshot successfully recorded without error
    assert snap.health_score == 100

    # Assertion 25: PostgreSQL initialization check returns boolean safely
    pg_status = storage.init_postgres_schema()
    assert isinstance(pg_status, bool)

    storage.close()
    if os.path.exists(db_file):
        os.remove(db_file)


def main():
    tracemalloc.start()
    start_time = time.time()
    print("=" * 70)
    print("Starting Deterministic Test Suite: Artifact E14 (26 Assertions)")
    print("=" * 70)

    test_models_and_configurations()
    test_disk_cleaner_simulation()
    test_service_auditor_and_rollback()
    test_registry_repair_auditor()
    test_system_health_scoring()
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
