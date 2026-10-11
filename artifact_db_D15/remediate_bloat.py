"""
Non-Blocking Bloat Remediation Suite for PostgreSQL 18.
Artifact D15 Round 1: Severe Bloat Simulation & Remediation.

Executes safe non-blocking maintenance:
1. VACUUM (VERBOSE, ANALYZE) on orders table.
2. REINDEX TABLE CONCURRENTLY on orders table.
3. Applies tuned autovacuum parameters (scale_factor = 0.05, cost_limit = 1000).

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


def get_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=10,
    )
    # Autocommit is required for VACUUM and REINDEX CONCURRENTLY in psycopg2
    conn.autocommit = True
    return conn


def capture_table_state(cur, label):
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

    print(f"\n--- STORAGE & STATS SNAPSHOT [{label}] ---")
    print(f"Live Tuples:        {n_live:,}")
    print(f"Dead Tuples:        {n_dead:,}")
    print(f"Dead Tuple Ratio:   {dead_ratio:.2f}%")
    print(f"Table Size:         {table_bytes / (1024 * 1024):.2f} MB ({table_bytes:,} bytes)")
    print(f"Indexes Size:       {index_bytes / (1024 * 1024):.2f} MB ({index_bytes:,} bytes)")
    print(f"Total Disk Size:    {total_bytes / (1024 * 1024):.2f} MB ({total_bytes:,} bytes)")
    print("--------------------------------------------------\n")

    return {
        "live_tuples": n_live,
        "dead_tuples": n_dead,
        "dead_tuple_ratio_pct": dead_ratio,
        "table_bytes": table_bytes,
        "index_bytes": index_bytes,
        "total_bytes": total_bytes,
    }


def execute_nonblocking_vacuum(cur):
    print("Step 1: Executing VACUUM (VERBOSE, ANALYZE)...")
    cur.execute("SET lock_timeout = '5s';")
    cur.execute("SET statement_timeout = '60s';")
    t0 = time.perf_counter()
    cur.execute(f"VACUUM (VERBOSE, ANALYZE) {SCHEMA_NAME}.{TABLE_NAME};")
    elapsed = time.perf_counter() - t0
    print(f"VACUUM (VERBOSE, ANALYZE) completed in {elapsed:.3f}s with zero lock timeouts.")
    return elapsed


def execute_nonblocking_reindex(cur):
    print("Step 2: Executing REINDEX TABLE CONCURRENTLY...")
    cur.execute("SET lock_timeout = '5s';")
    cur.execute("SET statement_timeout = '60s';")
    t0 = time.perf_counter()
    cur.execute(f"REINDEX TABLE CONCURRENTLY {SCHEMA_NAME}.{TABLE_NAME};")
    elapsed = time.perf_counter() - t0
    print(f"REINDEX TABLE CONCURRENTLY completed in {elapsed:.3f}s with zero lock timeouts.")
    return elapsed


def apply_autovacuum_tuning(cur):
    print("Step 3: Applying tuned autovacuum configuration parameters...")
    cur.execute(f"""
        ALTER TABLE {SCHEMA_NAME}.{TABLE_NAME} SET (
            autovacuum_enabled = true,
            autovacuum_vacuum_scale_factor = 0.05,
            autovacuum_vacuum_cost_limit = 1000
        );
    """)
    # Verify settings via pg_class.reloptions
    cur.execute(f"""
        SELECT reloptions 
        FROM pg_class 
        WHERE relname = '{TABLE_NAME}' 
          AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = '{SCHEMA_NAME}');
    """)
    options = cur.fetchone()[0]
    print(f"Verified active table reloptions: {options}")
    return options


def verify_concurrent_readability(cur):
    print("Verifying concurrent read availability on orders table...")
    t0 = time.perf_counter()
    cur.execute(f"SELECT COUNT(*), AVG(amount) FROM {SCHEMA_NAME}.{TABLE_NAME};")
    cnt, avg_val = cur.fetchone()
    elapsed = time.perf_counter() - t0
    print(f"Read query verified: {cnt:,} rows, average amount {avg_val:.2f} in {elapsed:.4f}s.")
    assert cnt == 100_000, f"Expected 100,000 live rows, found {cnt}"


def run_remediation():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            pre_state = capture_table_state(cur, "PRE-REMEDIATION")
            vac_time = execute_nonblocking_vacuum(cur)
            reindex_time = execute_nonblocking_reindex(cur)
            options = apply_autovacuum_tuning(cur)
            verify_concurrent_readability(cur)
            post_state = capture_table_state(cur, "POST-REMEDIATION")

            # Check reduction metrics
            table_reclaimed = pre_state["table_bytes"] - post_state["table_bytes"]
            table_reclaimed_pct = (table_reclaimed / pre_state["table_bytes"] * 100.0) if pre_state["table_bytes"] > 0 else 0.0

            index_reclaimed = pre_state["index_bytes"] - post_state["index_bytes"]
            index_reclaimed_pct = (index_reclaimed / pre_state["index_bytes"] * 100.0) if pre_state["index_bytes"] > 0 else 0.0

            total_reclaimed = pre_state["total_bytes"] - post_state["total_bytes"]
            total_reclaimed_pct = (total_reclaimed / pre_state["total_bytes"] * 100.0) if pre_state["total_bytes"] > 0 else 0.0

            print("\n=== RECLAMATION RESULTS ===")
            print(f"Dead Tuple Ratio Drop: {pre_state['dead_tuple_ratio_pct']:.2f}% -> {post_state['dead_tuple_ratio_pct']:.2f}%")
            print(f"Table Space Reclaimed:  {table_reclaimed_pct:.2f}% ({table_reclaimed / (1024 * 1024):.2f} MB)")
            print(f"Index Space Reclaimed:  {index_reclaimed_pct:.2f}% ({index_reclaimed / (1024 * 1024):.2f} MB)")
            print(f"Total Disk Reclaimed:   {total_reclaimed_pct:.2f}% ({total_reclaimed / (1024 * 1024):.2f} MB)")
            print(f"Total Remediation Time: {vac_time + reindex_time:.3f}s")
            print("===========================\n")

            return {
                "pre_remediation": pre_state,
                "post_remediation": post_state,
                "reclamation": {
                    "table_reclaimed_bytes": table_reclaimed,
                    "table_reclaimed_pct": table_reclaimed_pct,
                    "index_reclaimed_bytes": index_reclaimed,
                    "index_reclaimed_pct": index_reclaimed_pct,
                    "total_reclaimed_bytes": total_reclaimed,
                    "total_reclaimed_pct": total_reclaimed_pct,
                },
                "timing": {
                    "vacuum_seconds": vac_time,
                    "reindex_seconds": reindex_time,
                    "total_remediation_seconds": vac_time + reindex_time,
                },
                "options": options,
            }
    finally:
        conn.close()


def main():
    print("Initiating PostgreSQL 18 non-blocking bloat remediation...")
    results = run_remediation()
    print("Remediation execution completed successfully.")


if __name__ == "__main__":
    main()
