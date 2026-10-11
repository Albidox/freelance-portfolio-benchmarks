"""
Bloat Generator for PostgreSQL Table Maintenance Sandbox.
Artifact D15 Round 1: Severe Bloat Simulation & Remediation.

Creates table 'orders' in schema 'd15_vacuum_sandbox', populates 100,000
active records, and generates 80%+ dead tuple bloat through rapid batch inserts
and deletes.

Strict zero em dash policy enforced.
"""

import os
import sys
import time
import psycopg2

DB_HOST = os.getenv("PGHOST", "127.0.0.1")
DB_PORT = int(os.getenv("PGPORT", "5433"))
DB_NAME = os.getenv("PGDATABASE", "postgres")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
SCHEMA_NAME = "d15_vacuum_sandbox"
TABLE_NAME = "orders"
ACTIVE_ROWS = 100_000
BATCH_DELETED_ROWS = 400_000
TOTAL_ROWS = ACTIVE_ROWS + BATCH_DELETED_ROWS


def get_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=10,
    )
    conn.autocommit = True
    return conn


def setup_schema_and_table(cur):
    print(f"Initializing schema '{SCHEMA_NAME}' and table '{TABLE_NAME}'...")
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};")
    cur.execute(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.{TABLE_NAME} CASCADE;")
    cur.execute(f"""
        CREATE TABLE {SCHEMA_NAME}.{TABLE_NAME} (
            order_id BIGINT PRIMARY KEY,
            customer_id VARCHAR(64) NOT NULL,
            status VARCHAR(32) NOT NULL,
            amount NUMERIC(10, 2) NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        ) WITH (autovacuum_enabled = false);
    """)
    cur.execute(f"""
        CREATE INDEX idx_orders_customer_status 
        ON {SCHEMA_NAME}.{TABLE_NAME} (customer_id, status);
    """)
    print("Schema, table, and secondary index created successfully.")


def populate_initial_rows(cur):
    print(f"Populating {ACTIVE_ROWS:,} active baseline rows...")
    t0 = time.perf_counter()
    cur.execute(f"""
        INSERT INTO {SCHEMA_NAME}.{TABLE_NAME} (order_id, customer_id, status, amount, updated_at)
        SELECT
            i,
            'CUST_' || LPAD((i % 10000)::text, 6, '0'),
            CASE 
                WHEN i % 3 = 0 THEN 'PENDING'
                WHEN i % 3 = 1 THEN 'PROCESSING'
                ELSE 'COMPLETED'
            END,
            ROUND((15.50 + (i % 850) + (i % 99) * 0.01)::numeric, 2),
            NOW() - ((i % 86400) || ' seconds')::interval
        FROM generate_series(1, {ACTIVE_ROWS}) AS i;
    """)
    elapsed = time.perf_counter() - t0
    print(f"Populated {ACTIVE_ROWS:,} active rows in {elapsed:.3f}s ({ACTIVE_ROWS / elapsed:,.0f} rows/s).")


def generate_severe_bloat(cur):
    print("Executing in-page updates on active rows to generate line-pointer dead tuples...")
    t0 = time.perf_counter()
    cur.execute(f"""
        UPDATE {SCHEMA_NAME}.{TABLE_NAME}
        SET status = 'SHIPPED', amount = amount + 1.50, updated_at = NOW()
        WHERE order_id <= 10000;
    """)
    update_elapsed = time.perf_counter() - t0
    print(f"Updated 10,000 active rows in {update_elapsed:.3f}s.")

    print(f"Injecting {BATCH_DELETED_ROWS:,} temporary batch rows to inflate page storage...")
    t1 = time.perf_counter()
    cur.execute(f"""
        INSERT INTO {SCHEMA_NAME}.{TABLE_NAME} (order_id, customer_id, status, amount, updated_at)
        SELECT
            i,
            'CUST_' || LPAD((i % 10000)::text, 6, '0'),
            'TEMPORARY_BATCH',
            ROUND((10.00 + (i % 500))::numeric, 2),
            NOW()
        FROM generate_series({ACTIVE_ROWS + 1}, {TOTAL_ROWS}) AS i;
    """)
    insert_elapsed = time.perf_counter() - t1
    print(f"Batch rows inserted in {insert_elapsed:.3f}s.")

    print(f"Executing rapid deletes to generate dead tuple fragmentation...")
    t2 = time.perf_counter()
    cur.execute(f"DELETE FROM {SCHEMA_NAME}.{TABLE_NAME} WHERE order_id > {ACTIVE_ROWS};")
    delete_elapsed = time.perf_counter() - t2
    print(f"Deleted {BATCH_DELETED_ROWS:,} rows in {delete_elapsed:.3f}s.")


def capture_bloat_metrics(cur):
    cur.execute("SELECT pg_stat_force_next_flush();")
    cur.execute(f"""
        SELECT 
            n_live_tup, 
            n_dead_tup,
            pg_relation_size('{SCHEMA_NAME}.{TABLE_NAME}'::regclass) AS table_size,
            pg_indexes_size('{SCHEMA_NAME}.{TABLE_NAME}'::regclass) AS indexes_size,
            pg_total_relation_size('{SCHEMA_NAME}.{TABLE_NAME}'::regclass) AS total_size
        FROM pg_stat_user_tables
        WHERE schemaname = '{SCHEMA_NAME}' AND relname = '{TABLE_NAME}';
    """)
    row = cur.fetchone()
    if not row:
        raise RuntimeError("Failed to query pg_stat_user_tables for orders.")

    n_live, n_dead, table_bytes, index_bytes, total_bytes = row
    total_tuples = n_live + n_dead
    dead_ratio = (n_dead / total_tuples * 100.0) if total_tuples > 0 else 0.0

    print("\n--- BLOAT DIAGNOSTIC SUMMARY (PRE-REMEDIATION) ---")
    print(f"Live Tuples:        {n_live:,}")
    print(f"Dead Tuples:        {n_dead:,}")
    print(f"Dead Tuple Ratio:   {dead_ratio:.2f}%")
    print(f"Table Size:         {table_bytes / (1024 * 1024):.2f} MB ({table_bytes:,} bytes)")
    print(f"Indexes Size:       {index_bytes / (1024 * 1024):.2f} MB ({index_bytes:,} bytes)")
    print(f"Total Disk Size:    {total_bytes / (1024 * 1024):.2f} MB ({total_bytes:,} bytes)")
    print("--------------------------------------------------\n")

    if dead_ratio < 80.0:
        raise AssertionError(f"Dead tuple ratio {dead_ratio:.2f}% is below 80% threshold.")

    return {
        "live_tuples": n_live,
        "dead_tuples": n_dead,
        "dead_tuple_ratio_pct": dead_ratio,
        "table_bytes": table_bytes,
        "index_bytes": index_bytes,
        "total_bytes": total_bytes,
    }


def main():
    print("Connecting to PostgreSQL 18 on port 5433...")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            setup_schema_and_table(cur)
            populate_initial_rows(cur)
            generate_severe_bloat(cur)
            metrics = capture_bloat_metrics(cur)
        print("Bloat generation successfully completed. Acceptance gate >= 80% passed.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
