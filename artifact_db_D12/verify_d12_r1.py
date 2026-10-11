"""
Verification script for Artifact D12 Round 1 Sandbox Build.
Validates table row count, schema columns, performance metrics,
SHA-256 manifest generation, and zero em dash compliance.
Strict zero em dash policy enforced.
"""

import os
import sys
import json
import hashlib
import psycopg2

DB_HOST = os.getenv("PGHOST", "127.0.0.1")
DB_PORT = int(os.getenv("PGPORT", "5433"))
DB_NAME = os.getenv("PGDATABASE", "postgres")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
SCHEMA_NAME = "d12_copy_sandbox"
TABLE_NAME = "inventory"
EXPECTED_ROWS = 500_000
OUTPUT_DIR = "output"
METRICS_PATH = os.path.join(OUTPUT_DIR, "ingestion_metrics.json")
SHA256_PATH = os.path.join(OUTPUT_DIR, "SHA256SUMS.txt")


def calculate_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_database_state():
    print("Verifying PostgreSQL 18 state...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    try:
        with conn.cursor() as cur:
            # Check row count
            cur.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.{TABLE_NAME};")
            row_count = cur.fetchone()[0]
            print(f"Row count verified in {SCHEMA_NAME}.{TABLE_NAME}: {row_count:,}")
            assert row_count == EXPECTED_ROWS, f"Expected {EXPECTED_ROWS} rows, found {row_count}"

            # Check column definitions
            cur.execute(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = '{SCHEMA_NAME}' AND table_name = '{TABLE_NAME}'
                ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()
            print(f"Columns verified: {columns}")
            expected_cols = ["id", "sku", "name", "price", "stock", "category", "warehouse_id", "created_at"]
            col_names = [c[0] for c in columns]
            assert col_names == expected_cols, f"Column mismatch: {col_names} vs {expected_cols}"

            # Check sample row validity
            cur.execute(f"""
                SELECT id, sku, name, price, stock, category, warehouse_id, created_at
                FROM {SCHEMA_NAME}.{TABLE_NAME}
                LIMIT 5;
            """)
            sample = cur.fetchall()
            assert len(sample) == 5, "Sample rows count mismatch"
            print("Sample rows validated successfully.")
    finally:
        conn.close()


def verify_metrics_json():
    print(f"Verifying {METRICS_PATH}...")
    assert os.path.exists(METRICS_PATH), f"Metrics file not found: {METRICS_PATH}"
    with open(METRICS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["database"]["port"] == DB_PORT
    assert data["database"]["schema"] == SCHEMA_NAME
    assert data["dataset"]["verified_row_count"] == EXPECTED_ROWS
    assert data["performance"]["timing_gate_passed"] is True
    assert data["performance"]["total_elapsed_seconds"] < 5.0
    assert data["performance"]["rows_per_second"] > 100000.0
    assert data["memory"]["memory_gate_passed"] is True
    assert data["memory"]["peak_rss_mb"] <= 35.0
    assert data["acceptance_criteria_verified"] is True
    print(f"Metrics verification passed: {data['performance']['rows_per_second']:,} rows/s in {data['performance']['total_elapsed_seconds']}s, peak RAM {data['memory']['peak_rss_mb']}MB.")


def generate_sha256_manifest():
    print("Generating SHA-256 checksum manifest...")
    target_files = [
        "generate_massive_dataset.py",
        "ingest_pipeline.py",
        "benchmark_ingestion.py",
        "init_db.py",
        "README.md",
        "requirements.txt",
        os.path.join(OUTPUT_DIR, "ingestion_metrics.json"),
        os.path.join(OUTPUT_DIR, "benchmark_comparison.json"),
    ]

    manifest_lines = []
    for rel_path in sorted(target_files):
        if os.path.exists(rel_path):
            checksum = calculate_sha256(rel_path)
            # Normalize path slashes for manifest
            norm_path = rel_path.replace("\\", "/")
            manifest_lines.append(f"{checksum}  {norm_path}\n")
            print(f"  {checksum}  {norm_path}")

    with open(SHA256_PATH, "w", encoding="utf-8") as f:
        f.writelines(manifest_lines)
    print(f"Manifest written to {SHA256_PATH}")


def check_zero_em_dashes():
    print("Scanning codebase and outputs for em dash policy violations...")
    files_to_check = [
        "generate_massive_dataset.py",
        "ingest_pipeline.py",
        "benchmark_ingestion.py",
        "init_db.py",
        "verify_d12_r1.py",
        "README.md",
        "requirements.txt",
        os.path.join(OUTPUT_DIR, "ingestion_metrics.json"),
        os.path.join(OUTPUT_DIR, "benchmark_comparison.json"),
        SHA256_PATH,
    ]
    em_dash_codepoints = ["\u2014", "\u2013"]

    violations = []
    for fp in files_to_check:
        if os.path.exists(fp):
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                for em in em_dash_codepoints:
                    if em in content:
                        violations.append((fp, hex(ord(em))))

    if violations:
        print(f"FAILURE: Em dash violations found: {violations}")
        sys.exit(1)
    else:
        print("PASS: Zero em dashes found across all source and output files.")


def main():
    verify_database_state()
    verify_metrics_json()
    generate_sha256_manifest()
    check_zero_em_dashes()
    print("\nALL D12 ROUND 1 ACCEPTANCE CRITERIA VERIFIED SUCCESSFULLY.")


if __name__ == "__main__":
    main()
