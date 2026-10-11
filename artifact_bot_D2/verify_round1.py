"""
Round 1 Verification and Checksum Manifest Generator for Artifact D2.
Rule: Strict zero em dashes across all files and outputs.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def check_zero_em_dashes(root_dir: str) -> None:
    print("\nScanning repository files for em dash violations...")
    violations = []
    ignored_dirs = {".venv", ".git", "__pycache__"}

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in ignored_dirs]
        for fname in filenames:
            if fname.endswith((".py", ".sql", ".txt", ".md", ".json")):
                fpath = os.path.join(dirpath, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                        if chr(0x2014) in content:
                            violations.append(fpath)
                except Exception as e:
                    print(f"Warning: could not inspect {fpath}: {e}")

    if violations:
        print("FAIL: Em dash violations found in:")
        for v in violations:
            print(f"  {v}")
        raise ValueError(f"Found em dashes in {len(violations)} files.")
    else:
        print("PASS: Strict zero em dashes verified across all repository files.")


def generate_sha256_manifest(root_dir: str) -> None:
    print("\nGenerating output/SHA256SUMS.txt manifest...")
    target_files = [
        "schema.sql",
        "requirements.txt",
        "bot.py",
        "mock_job_generator.py",
        "verify_round1.py",
        "stress_probe.py",
        "output/r1_metrics.json",
        "output/r2_metrics.json",
        "output/telegram_resilience_probe_report.md",
    ]

    lines = []
    for rel_path in target_files:
        full_path = os.path.join(root_dir, rel_path)
        if os.path.exists(full_path):
            sha = compute_sha256(full_path)
            # Store in standard sha256sum format
            formatted = f"{sha}  {rel_path.replace(os.sep, '/')}\n"
            lines.append(formatted)
            print(f"  {sha}  {rel_path}")
        else:
            print(f"  WARNING: Missing {rel_path}")

    out_dir = os.path.join(root_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    manifest_path = os.path.join(out_dir, "SHA256SUMS.txt")
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(lines)
    print(f"Manifest successfully written to {manifest_path}")


def main() -> None:
    root_dir = os.path.abspath(os.path.dirname(__file__))

    # Step 1: Check zero em dashes
    check_zero_em_dashes(root_dir)

    # Step 2: Verify metrics from output/r1_metrics.json
    metrics_path = os.path.join(root_dir, "output", "r1_metrics.json")
    if not os.path.exists(metrics_path):
        raise FileNotFoundError(f"Missing {metrics_path}. Run 'python bot.py --benchmark' first.")

    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    print("\nVerifying Round 1 Acceptance Gates:")
    print(f"1. Total Processed: {metrics['total_processed']} (Expected: 100)")
    assert metrics["total_processed"] == 100
    print(f"2. Unique Leads Recorded: {metrics['unique_leads_recorded']} (Expected: 70)")
    assert metrics["unique_leads_recorded"] == 70
    print(f"3. Duplicates Dropped: {metrics['duplicates_suppressed']} (Expected: 30)")
    assert metrics["duplicates_suppressed"] == 30
    print(f"4. Database Lock Timeouts: {metrics['lock_timeouts']} (Expected: 0)")
    assert metrics["lock_timeouts"] == 0
    print(f"5. Alert Delivery Max Latency: {metrics['max_latency_seconds']}s (Expected: < 5.0s)")
    assert metrics["max_latency_seconds"] < 5.0
    print(f"6. Peak Working Set (RSS): {metrics['peak_rss_mb']} MB (Expected: < 30.0 MB)")
    assert metrics["peak_rss_mb"] < 30.0

    print("PASS: All Round 1 Acceptance Gates Satisfied.")

    # Step 3: Generate SHA-256 Manifest
    generate_sha256_manifest(root_dir)

    print("\n========================================================")
    print("ROUND 1 VERIFICATION COMPLETED WITH ZERO DEFECTS.")
    print("========================================================")


if __name__ == "__main__":
    main()
