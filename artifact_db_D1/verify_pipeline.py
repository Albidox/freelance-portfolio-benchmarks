#!/usr/bin/env python3
"""
verify_pipeline.py
End-to-end verification harness for Flyway migration repair pipeline.
Executes Flyway migrate post-repair, verifies exit code 0, confirms V4 applied,
validates schema integrity, generates SHA-256 manifest, and verifies zero em dashes.

Zero em dashes policy enforced.
"""

import os
import sys
import subprocess
import hashlib
import json
import psycopg2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
RECEIPT_FILE = os.path.join(OUTPUT_DIR, "repair_receipt.json")
SHA256_MANIFEST = os.path.join(OUTPUT_DIR, "SHA256SUMS.txt")

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "user": "postgres",
    "password": "",
    "dbname": "artifact_d1_db"
}


def run_flyway_migrate():
    print("[1/5] Executing Flyway migrate post-repair...")
    cmd = ["mvn.cmd", "flyway:migrate"]
    result = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        print("ERROR: Flyway migration failed with non-zero exit code:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)
    print("      Flyway migrate completed successfully with exit code 0.")


def verify_database_state():
    print("[2/5] Inspecting flyway_schema_history and database state...")
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT installed_rank, version, description, script, checksum, success
        FROM flyway_schema_history
        ORDER BY installed_rank;
    """)
    rows = cursor.fetchall()
    print(f"      Found {len(rows)} migrations in history table:")
    for r in rows:
        print(f"        Rank {r[0]} | Version {r[1]} | {r[3]} | Checksum: {r[4]} | Success: {r[5]}")

    if len(rows) != 4:
        print(f"ERROR: Expected 4 applied migrations, found {len(rows)}.")
        sys.exit(1)

    for r in rows:
        if not r[5]:
            print(f"ERROR: Migration version {r[1]} has success = False.")
            sys.exit(1)

    # Check V4 script applied
    v4_row = rows[3]
    if v4_row[1] != "4" or "V4__add_audit_indexes.sql" not in v4_row[3]:
        print(f"ERROR: Version 4 was not applied cleanly. Found: {v4_row}")
        sys.exit(1)

    # Verify schema objects
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('tenants', 'users', 'orders');
    """)
    tables = [t[0] for t in cursor.fetchall()]
    assert "tenants" in tables, "Table tenants missing"
    assert "users" in tables, "Table users missing"
    assert "orders" in tables, "Table orders missing"

    # Verify orders.metadata JSONB column
    cursor.execute("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_name = 'orders' AND column_name = 'metadata';
    """)
    col = cursor.fetchone()
    assert col is not None and col[1] == "jsonb", "Column orders.metadata jsonb missing"

    # Verify partial index on orders
    cursor.execute("""
        SELECT indexname FROM pg_indexes 
        WHERE tablename = 'orders' AND indexname = 'idx_orders_active_recent';
    """)
    idx = cursor.fetchone()
    assert idx is not None, "Index idx_orders_active_recent missing on orders"

    cursor.close()
    conn.close()
    print("      Database schema verification: 100% green.")


def verify_repair_receipt():
    print("[3/5] Validating repair receipt...")
    if not os.path.isfile(RECEIPT_FILE):
        print(f"ERROR: Receipt file {RECEIPT_FILE} does not exist.")
        sys.exit(1)

    with open(RECEIPT_FILE, "r", encoding="utf-8") as f:
        receipt = json.load(f)

    assert receipt["status"] == "SUCCESS", "Receipt status is not SUCCESS"
    assert receipt["summary"]["performance_passed"] is True, "Performance SLA failed"
    assert len(receipt["repairs"]) >= 1, "No repairs recorded in receipt"
    v3_repair = next((r for r in receipt["repairs"] if r["version"] == "3"), None)
    assert v3_repair is not None, "Version 3 repair missing from receipt"
    assert v3_repair["checksum_before"] != v3_repair["checksum_after"], "Checksum before and after must differ"
    print(f"      Receipt confirmed: V3 repaired from {v3_repair['checksum_before']} to {v3_repair['checksum_after']}.")


def generate_sha256_manifest():
    print("[4/5] Generating SHA-256 manifest in output/SHA256SUMS.txt...")
    files_to_hash = [
        "schema_setup.sql",
        "pom.xml",
        "migrations/V1__init_schema.sql",
        "migrations/V2__add_orders.sql",
        "migrations/V3__add_metadata.sql",
        "migrations/V4__add_audit_indexes.sql",
        "setup_corrupted_state.py",
        "repair_migration.py",
        "stress_probe_engine.py",
        "verify_pipeline.py",
        "output/repair_receipt.json",
        "output/real_world_migration_failure_report.md"
    ]

    manifest_lines = []
    for rel_path in sorted(files_to_hash):
        abs_path = os.path.join(BASE_DIR, rel_path)
        if not os.path.isfile(abs_path):
            continue
        h = hashlib.sha256()
        with open(abs_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        digest = h.hexdigest()
        normalized_name = rel_path.replace("\\", "/")
        manifest_lines.append(f"{digest}  {normalized_name}")

    with open(SHA256_MANIFEST, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(manifest_lines) + "\n")

    print(f"      SHA-256 manifest written ({len(manifest_lines)} artifacts hashed).")


def verify_punctuation_rule():
    print("[5/5] Auditing strict zero em dashes rule across workspace...")
    disallowed = ["\u2014", "\u2013", "\u2015"]
    scanned = 0
    for root, _, files in os.walk(BASE_DIR):
        if ".venv" in root or ".git" in root or "target" in root:
            continue
        for fname in files:
            if fname.endswith((".py", ".sql", ".xml", ".json", ".txt", ".md")):
                fpath = os.path.join(root, fname)
                scanned += 1
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                for char in disallowed:
                    if char in content:
                        print(f"ERROR: Em dash character found in {fpath}")
                        sys.exit(1)
    print(f"      Punctuation audit passed: {scanned} text files checked with zero em dashes.")


def main():
    print("=== Commencing Pipeline Verification ===")
    run_flyway_migrate()
    verify_database_state()
    verify_repair_receipt()
    generate_sha256_manifest()
    verify_punctuation_rule()
    print("=== All Round 1 Acceptance Gates Passed Successfully ===")


if __name__ == "__main__":
    main()
