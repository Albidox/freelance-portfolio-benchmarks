"""
benchmark_sanitizer.py: Performance and compliance benchmark suite.
Measures execution speed, memory usage, error detection accuracy,
and generates complete SHA-256 verification manifest.
Strict constraint: Zero em dashes.
"""

import os
import sys
import time
import json
import hashlib
import psutil
from typing import Dict, Any, List

from generate_dirty_data import generate_dirty_dataset
from clean_pipeline import run_pipeline

def calculate_sha256(filepath: str) -> str:
    """Calculates SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def verify_quarantine_integrity(quarantine_path: str) -> Dict[str, Any]:
    """
    Verifies that 100% of quarantined records contain valid row indices
    and exact JSON field validation error paths.
    """
    total_quarantined = 0
    records_with_valid_error_paths = 0
    field_error_distribution: Dict[str, int] = {}

    with open(quarantine_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            total_quarantined += 1
            entry = json.loads(line)

            assert "row_index" in entry, f"Missing row_index at line {idx}"
            assert "raw_record" in entry, f"Missing raw_record at line {idx}"
            assert "validation_errors" in entry, f"Missing validation_errors at line {idx}"

            errors = entry["validation_errors"]
            assert len(errors) > 0, f"Empty validation_errors at line {idx}"

            has_valid_loc = True
            for err in errors:
                assert "loc" in err, f"Missing loc in error at line {idx}"
                assert "msg" in err, f"Missing msg in error at line {idx}"
                assert "type" in err, f"Missing type in error at line {idx}"
                loc_list = err["loc"]
                if not loc_list or not isinstance(loc_list, list):
                    has_valid_loc = False
                for field_name in loc_list:
                    field_error_distribution[str(field_name)] = field_error_distribution.get(str(field_name), 0) + 1

            if has_valid_loc:
                records_with_valid_error_paths += 1

    accuracy_pct = (records_with_valid_error_paths / total_quarantined * 100.0) if total_quarantined > 0 else 100.0

    return {
        "total_quarantined_checked": total_quarantined,
        "valid_path_records": records_with_valid_error_paths,
        "path_compliance_percentage": round(accuracy_pct, 4),
        "field_error_distribution": field_error_distribution
    }

def run_benchmark():
    input_file = "data/dirty_records.jsonl"
    output_parquet = "output/cleaned_records.parquet"
    output_quarantine = "output/quarantined_records.jsonl"
    metrics_path = "output/sanitizer_metrics.json"
    manifest_path = "output/SHA256SUMS.txt"

    print("=================================================================")
    print("D14-R1: 100,000 Dirty Record Sanitizer Benchmark")
    print("=================================================================")

    # Step 1: Ensure dirty test data exists
    if not os.path.exists(input_file):
        print(f"Generating 100,000 synthetic records into {input_file}...")
        generate_dirty_dataset(input_file, count=100000)
    else:
        print(f"Using existing input file: {input_file}")

    # Step 2: Measure memory and run pipeline
    process = psutil.Process(os.getpid())
    mem_before_bytes = process.memory_info().rss

    print("Executing streaming sanitization pipeline...")
    pipeline_result = run_pipeline(
        input_source=input_file,
        output_parquet_path=output_parquet,
        output_quarantine_path=output_quarantine,
        batch_size=10000
    )

    mem_after_bytes = process.memory_info().rss
    peak_mem_mb = max(mem_before_bytes, mem_after_bytes) / (1024 * 1024)

    # Step 3: Verify quarantine integrity
    print("Verifying quarantine integrity and error paths...")
    quarantine_audit = verify_quarantine_integrity(output_quarantine)

    # Step 4: Validate acceptance criteria
    total_processed = pipeline_result["total_records_processed"]
    elapsed_time = pipeline_result["execution_time_seconds"]
    throughput = pipeline_result["throughput_records_per_second"]
    uncaught_exceptions = pipeline_result["uncaught_runtime_exceptions"]
    compliance_pct = quarantine_audit["path_compliance_percentage"]

    passed_time_gate = elapsed_time < 2.5 and throughput >= 40000.0
    passed_exception_gate = (uncaught_exceptions == 0)
    passed_quarantine_gate = (compliance_pct == 100.0)

    print("\n--- Gate Verification Results ---")
    print(f"Total Processed: {total_processed:,} records")
    print(f"Execution Time: {elapsed_time:.4f}s (Threshold: < 2.50s) -> {'PASS' if passed_time_gate else 'FAIL'}")
    print(f"Throughput: {throughput:,.2f} records/sec (Threshold: >= 40,000/sec) -> {'PASS' if passed_time_gate else 'FAIL'}")
    print(f"Uncaught Exceptions: {uncaught_exceptions} (Threshold: 0) -> {'PASS' if passed_exception_gate else 'FAIL'}")
    print(f"Error Path Compliance: {compliance_pct:.2f}% (Threshold: 100.0%) -> {'PASS' if passed_quarantine_gate else 'FAIL'}")
    print(f"Peak Memory RSS: {peak_mem_mb:.2f} MB")

    all_gates_passed = passed_time_gate and passed_exception_gate and passed_quarantine_gate

    metrics_payload = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifact_id": "D14",
        "round": "R1",
        "status": "PASSED" if all_gates_passed else "FAILED",
        "total_records_processed": total_processed,
        "valid_records_count": pipeline_result["valid_records_count"],
        "quarantined_records_count": pipeline_result["quarantined_records_count"],
        "uncaught_runtime_exceptions": uncaught_exceptions,
        "execution_time_seconds": elapsed_time,
        "throughput_records_per_second": throughput,
        "peak_memory_rss_mb": round(peak_mem_mb, 2),
        "quarantine_error_path_compliance_pct": compliance_pct,
        "field_error_distribution": quarantine_audit["field_error_distribution"],
        "acceptance_criteria": {
            "under_2_point_5_seconds": passed_time_gate,
            "zero_uncaught_exceptions": passed_exception_gate,
            "hundred_pct_error_paths": passed_quarantine_gate
        }
    }

    # Step 5: Save metrics
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)
    print(f"\nSaved metrics to {metrics_path}")

    # Step 6: Generate SHA-256 manifest
    files_to_hash = [
        output_parquet,
        output_quarantine,
        metrics_path
    ]

    manifest_lines = []
    print("\nSHA-256 Checksums:")
    for fp in files_to_hash:
        rel_path = os.path.relpath(fp, start=".").replace("\\", "/")
        file_hash = calculate_sha256(fp)
        manifest_lines.append(f"{file_hash}  {rel_path}\n")
        print(f"  {file_hash}  {rel_path}")

    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(manifest_lines)
    print(f"Generated SHA-256 manifest at {manifest_path}")

    if not all_gates_passed:
        print("\nERROR: Acceptance criteria check failed!")
        sys.exit(1)

    print("\nALL D14-R1 ACCEPTANCE GATES PASSED DETERMINISTICALLY.")

if __name__ == "__main__":
    run_benchmark()
