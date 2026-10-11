"""
Concurrent Read/Write Stress Probe for PostgreSQL Maintenance Suite.
Artifact D15 Round 2: Real-World Stress Probe & Concurrency Lock Audit.

Executes non-blocking bloat remediation (VACUUM and REINDEX CONCURRENTLY)
while 50 parallel client threads fire continuous SELECT and INSERT queries.
Asserts zero lock timeouts, zero aborted transactions, and zero query failures.

Strict zero em dash policy enforced.
"""

import os
import sys
import time
import threading
import statistics
import psycopg2

DB_HOST = os.getenv("PGHOST", "127.0.0.1")
DB_PORT = int(os.getenv("PGPORT", "5433"))
DB_NAME = os.getenv("PGDATABASE", "postgres")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
SCHEMA_NAME = "d15_vacuum_sandbox"
TABLE_NAME = "orders"
NUM_READERS = 25
NUM_WRITERS = 25
TOTAL_WORKERS = NUM_READERS + NUM_WRITERS


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


def run_concurrency_stress_probe():
    print("=" * 60)
    print("PROBE 1: CONCURRENT READ/WRITE STRESS PROBE")
    print(f"Target: {SCHEMA_NAME}.{TABLE_NAME} under 50 concurrent worker threads")
    print(f"Workers: {NUM_READERS} readers, {NUM_WRITERS} writers")
    print("=" * 60)

    stop_event = threading.Event()
    stats_lock = threading.Lock()

    metrics = {
        "read_queries": 0,
        "write_queries": 0,
        "total_queries": 0,
        "lock_timeouts": 0,
        "aborted_transactions": 0,
        "query_errors": 0,
        "read_latencies_ms": [],
        "write_latencies_ms": [],
        "error_details": [],
        "vacuum_duration_seconds": 0.0,
        "reindex_duration_seconds": 0.0,
        "total_remediation_seconds": 0.0,
    }

    def reader_worker(worker_id):
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute("SET lock_timeout = '5s';")
                cur.execute("SET statement_timeout = '15s';")
                while not stop_event.is_set():
                    cid = f"CUST_{(worker_id * 37) % 10000:06d}"
                    t0 = time.perf_counter()
                    cur.execute(
                        f"SELECT order_id, customer_id, amount, status FROM {SCHEMA_NAME}.{TABLE_NAME} WHERE customer_id = '{cid}' LIMIT 10;"
                    )
                    _ = cur.fetchall()
                    lat_ms = (time.perf_counter() - t0) * 1000.0

                    with stats_lock:
                        metrics["read_queries"] += 1
                        metrics["total_queries"] += 1
                        if len(metrics["read_latencies_ms"]) < 5000:
                            metrics["read_latencies_ms"].append(lat_ms)
            conn.close()
        except Exception as exc:
            err_msg = str(exc)
            with stats_lock:
                metrics["query_errors"] += 1
                if "lock timeout" in err_msg.lower() or "57014" in err_msg:
                    metrics["lock_timeouts"] += 1
                else:
                    metrics["aborted_transactions"] += 1
                metrics["error_details"].append(f"Reader {worker_id}: {err_msg}")

    def writer_worker(worker_id):
        seq = 0
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute("SET lock_timeout = '5s';")
                cur.execute("SET statement_timeout = '15s';")
                while not stop_event.is_set():
                    seq += 1
                    oid = 5000000 + (worker_id * 500000) + seq
                    cid = f"CUST_{(seq % 10000):06d}"
                    amt = 25.00 + (seq % 200)
                    t0 = time.perf_counter()
                    cur.execute(
                        f"INSERT INTO {SCHEMA_NAME}.{TABLE_NAME} (order_id, customer_id, status, amount, updated_at) "
                        f"VALUES ({oid}, '{cid}', 'PROCESSING', {amt:.2f}, NOW());"
                    )
                    lat_ms = (time.perf_counter() - t0) * 1000.0

                    with stats_lock:
                        metrics["write_queries"] += 1
                        metrics["total_queries"] += 1
                        if len(metrics["write_latencies_ms"]) < 5000:
                            metrics["write_latencies_ms"].append(lat_ms)
            conn.close()
        except Exception as exc:
            err_msg = str(exc)
            with stats_lock:
                metrics["query_errors"] += 1
                if "lock timeout" in err_msg.lower() or "57014" in err_msg:
                    metrics["lock_timeouts"] += 1
                else:
                    metrics["aborted_transactions"] += 1
                metrics["error_details"].append(f"Writer {worker_id}: {err_msg}")

    threads = []
    print("Launching 50 concurrent client threads...")
    for i in range(NUM_READERS):
        t = threading.Thread(target=reader_worker, args=(i,), daemon=True)
        threads.append(t)
        t.start()

    for i in range(NUM_WRITERS):
        t = threading.Thread(target=writer_worker, args=(i,), daemon=True)
        threads.append(t)
        t.start()

    # Allow load to establish
    time.sleep(1.0)
    print("Concurrent client workload active. Initiating non-blocking maintenance...")

    conn = get_connection()
    t_start_remediation = time.perf_counter()
    try:
        with conn.cursor() as cur:
            cur.execute("SET lock_timeout = '10s';")
            print("Step 1: Executing VACUUM (VERBOSE, ANALYZE) under 50-thread concurrent load...")
            t0 = time.perf_counter()
            cur.execute(f"VACUUM (VERBOSE, ANALYZE) {SCHEMA_NAME}.{TABLE_NAME};")
            metrics["vacuum_duration_seconds"] = round(time.perf_counter() - t0, 4)
            print(f"VACUUM completed in {metrics['vacuum_duration_seconds']}s.")

            print("Step 2: Executing REINDEX TABLE CONCURRENTLY under 50-thread concurrent load...")
            t1 = time.perf_counter()
            cur.execute(f"REINDEX TABLE CONCURRENTLY {SCHEMA_NAME}.{TABLE_NAME};")
            metrics["reindex_duration_seconds"] = round(time.perf_counter() - t1, 4)
            print(f"REINDEX TABLE CONCURRENTLY completed in {metrics['reindex_duration_seconds']}s.")
    finally:
        conn.close()

    metrics["total_remediation_seconds"] = round(time.perf_counter() - t_start_remediation, 4)

    # Let threads run for 0.5s post-maintenance to verify stability
    time.sleep(0.5)
    print("Stopping client worker threads...")
    stop_event.set()

    for t in threads:
        t.join(timeout=5.0)

    # Calculate latency percentiles
    r_lats = sorted(metrics["read_latencies_ms"]) if metrics["read_latencies_ms"] else [0.0]
    w_lats = sorted(metrics["write_latencies_ms"]) if metrics["write_latencies_ms"] else [0.0]

    read_p50 = round(statistics.median(r_lats), 3)
    read_p95 = round(r_lats[int(len(r_lats) * 0.95)], 3)
    read_p99 = round(r_lats[int(len(r_lats) * 0.99)], 3)

    write_p50 = round(statistics.median(w_lats), 3)
    write_p95 = round(w_lats[int(len(w_lats) * 0.95)], 3)
    write_p99 = round(w_lats[int(len(w_lats) * 0.99)], 3)

    overall_qps = round(metrics["total_queries"] / metrics["total_remediation_seconds"], 1)

    print("\n--- CONCURRENCY STRESS PROBE AUDIT REPORT ---")
    print(f"Total Client Threads:     {TOTAL_WORKERS} (25 readers, 25 writers)")
    print(f"Total Queries Executed:   {metrics['total_queries']:,}")
    print(f"Read Queries Completed:   {metrics['read_queries']:,}")
    print(f"Write Queries Completed:  {metrics['write_queries']:,}")
    print(f"Throughput Under Load:    {overall_qps:,} queries/sec")
    print(f"Lock Timeouts Observed:   {metrics['lock_timeouts']}")
    print(f"Aborted Transactions:     {metrics['aborted_transactions']}")
    print(f"Query Errors:             {metrics['query_errors']}")
    print(f"VACUUM Duration:          {metrics['vacuum_duration_seconds']}s")
    print(f"REINDEX CONCURRENTLY:     {metrics['reindex_duration_seconds']}s")
    print(f"Total Remediation Time:   {metrics['total_remediation_seconds']}s")
    print(f"Read Latency (ms):        p50={read_p50}ms, p95={read_p95}ms, p99={read_p99}ms")
    print(f"Write Latency (ms):       p50={write_p50}ms, p95={write_p95}ms, p99={write_p99}ms")
    print("-" * 60)

    # Assertions required by specification
    assert metrics["lock_timeouts"] == 0, f"Expected 0 lock timeouts, got {metrics['lock_timeouts']}"
    assert metrics["aborted_transactions"] == 0, f"Expected 0 aborted transactions, got {metrics['aborted_transactions']}"
    assert metrics["query_errors"] == 0, f"Expected 0 query errors, got {metrics['query_errors']}"
    assert metrics["total_queries"] > 5000, f"Expected > 5000 queries, got {metrics['total_queries']}"
    print("VERIFICATION PASS: Zero lock timeouts, zero aborted transactions, and zero query failures.")

    return {
        "status": "PASSED",
        "total_workers": TOTAL_WORKERS,
        "num_readers": NUM_READERS,
        "num_writers": NUM_WRITERS,
        "total_queries": metrics["total_queries"],
        "read_queries": metrics["read_queries"],
        "write_queries": metrics["write_queries"],
        "throughput_qps": overall_qps,
        "lock_timeouts": metrics["lock_timeouts"],
        "aborted_transactions": metrics["aborted_transactions"],
        "query_errors": metrics["query_errors"],
        "timing": {
            "vacuum_seconds": metrics["vacuum_duration_seconds"],
            "reindex_seconds": metrics["reindex_duration_seconds"],
            "total_remediation_seconds": metrics["total_remediation_seconds"],
        },
        "latencies_ms": {
            "read": {"p50": read_p50, "p95": read_p95, "p99": read_p99},
            "write": {"p50": write_p50, "p95": write_p95, "p99": write_p99},
        },
    }


if __name__ == "__main__":
    run_concurrency_stress_probe()
