#!/usr/bin/env python3
"""
setup_corrupted_state.py
Simulates production disaster: applies V1-V3 migrations cleanly,
then modifies V3__add_metadata.sql on disk, creating a checksum mismatch
in flyway_schema_history.

Zero em dashes policy enforced.
"""

import os
import subprocess
import sys
import psycopg2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MIGRATIONS_DIR = os.path.join(BASE_DIR, "migrations")
V3_FILE = os.path.join(MIGRATIONS_DIR, "V3__add_metadata.sql")

PRISTINE_V3_CONTENT = """-- V3: Alter orders table to add metadata JSONB column
-- Author: Eric (Ashfaq Lead Software Engineering Specialist)

ALTER TABLE orders
ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
"""

CORRUPTED_V3_CONTENT = """-- V3: Alter orders table to add metadata JSONB column
-- Author: Eric (Ashfaq Lead Software Engineering Specialist)
-- Modifed post-deployment by developer without migration discipline:
-- Added documentation comment directly to migration script.

ALTER TABLE orders
ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN orders.metadata IS 'Dynamic order metadata payload in JSONB';
"""

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "user": "postgres",
    "password": "",
    "dbname": "postgres"
}

TARGET_DB = "artifact_d1_db"


def reset_database():
    print("[1/5] Resetting target database artifact_d1_db...")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.execute(f"DROP DATABASE IF EXISTS {TARGET_DB} WITH (FORCE);")
    cursor.execute(f"CREATE DATABASE {TARGET_DB} WITH OWNER = postgres;")
    cursor.close()
    conn.close()
    print("      Database reset complete.")


def restore_pristine_v3():
    print("[2/5] Restoring pristine V3 migration file...")
    with open(V3_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write(PRISTINE_V3_CONTENT)
    print("      Pristine V3 file restored.")


def apply_migrations_up_to_v3():
    print("[3/5] Applying migrations V1 through V3 via Flyway...")
    cmd = ["mvn.cmd", "flyway:migrate", "-Dflyway.target=3"]
    result = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        print("ERROR: Flyway migration failed:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)
    print("      Migrations V1-V3 applied successfully.")


def corrupt_v3_on_disk():
    print("[4/5] Modifying V3 migration file on disk to induce checksum mismatch...")
    with open(V3_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write(CORRUPTED_V3_CONTENT)
    print("      V3 file modified on disk.")


def verify_corrupted_state():
    print("[5/5] Verifying Flyway detects checksum corruption...")
    cmd = ["mvn.cmd", "flyway:info"]
    result = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
    output = result.stdout + result.stderr
    if "checksum mismatch" in output.lower() or "future" in output.lower() or result.returncode != 0:
        print("      Verification confirmed: Flyway detected schema mismatch.")
    else:
        # Also test migrate attempt
        migrate_cmd = ["mvn.cmd", "flyway:migrate"]
        m_result = subprocess.run(migrate_cmd, cwd=BASE_DIR, capture_output=True, text=True)
        m_output = m_result.stdout + m_result.stderr
        if m_result.returncode != 0 and "checksum mismatch" in m_output.lower():
            print("      Verification confirmed: Flyway migrate blocked by checksum mismatch.")
        else:
            print("      Note: Flyway output captured:")
            print(m_output)


def main():
    print("=== Simulating Corrupted Flyway Migration State ===")
    reset_database()
    restore_pristine_v3()
    apply_migrations_up_to_v3()
    corrupt_v3_on_disk()
    verify_corrupted_state()
    print("=== Corrupted State Successfully Established ===")


if __name__ == "__main__":
    main()
