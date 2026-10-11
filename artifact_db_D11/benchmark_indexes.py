"""
Benchmark script for Artifact D11 (PostgreSQL Partial and Composite Index Optimization).
Compares Sequential Scan vs Full Composite Index vs Optimized Partial Index.
Measures latency distribution (p50, p95, p99), shared buffers, and physical relation disk footprint.
"""

import os
import sys
import time
import json
import hashlib
import statistics
from pathlib import Path
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


DB_HOST = os.getenv("PGHOST", "127.0.0.1")
DB_PORT = int(os.getenv("PGPORT", "5433"))
DB_NAME = os.getenv("PGDATABASE", "postgres")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
SCHEMA_NAME = "d11_indexing_sandbox"
TABLE_NAME = "orders"
COMPOSITE_INDEX = "idx_orders_composite_status_created"
PARTIAL_INDEX = "idx_orders_partial_active_created"

BENCHMARK_QUERY = f"""
    SELECT * FROM {SCHEMA_NAME}.{TABLE_NAME}
    WHERE status = 'ACTIVE'
    ORDER BY created_at DESC
    LIMIT 50;
"""

OUTPUT_DIR = Path("output")


def get_connection(autocommit: bool = True):
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    if autocommit:
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def format_bytes(num_bytes: int) -> str:
    for unit in ["bytes", "KB", "MB", "GB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} TB"


def get_relation_sizes(conn):
    sizes = {}
    with conn.cursor() as cur:
        # Table size
        cur.execute(f"SELECT pg_relation_size('{SCHEMA_NAME}.{TABLE_NAME}'::regclass);")
        sizes["table_bytes"] = cur.fetchone()[0]
        sizes["table_pretty"] = format_bytes(sizes["table_bytes"])

        # Total relation size including all indexes and toast
        cur.execute(f"SELECT pg_total_relation_size('{SCHEMA_NAME}.{TABLE_NAME}'::regclass);")
        sizes["total_relation_bytes"] = cur.fetchone()[0]
        sizes["total_relation_pretty"] = format_bytes(sizes["total_relation_bytes"])

        # Check composite index size if exists
        cur.execute(f"""
            SELECT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = '{SCHEMA_NAME}' AND c.relname = '{COMPOSITE_INDEX}'
            );
        """)
        if cur.fetchone()[0]:
            cur.execute(f"SELECT pg_relation_size('{SCHEMA_NAME}.{COMPOSITE_INDEX}'::regclass);")
            sizes["composite_index_bytes"] = cur.fetchone()[0]
            sizes["composite_index_pretty"] = format_bytes(sizes["composite_index_bytes"])
        else:
            sizes["composite_index_bytes"] = 0
            sizes["composite_index_pretty"] = "0 bytes"

        # Check partial index size if exists
        cur.execute(f"""
            SELECT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = '{SCHEMA_NAME}' AND c.relname = '{PARTIAL_INDEX}'
            );
        """)
        if cur.fetchone()[0]:
            cur.execute(f"SELECT pg_relation_size('{SCHEMA_NAME}.{PARTIAL_INDEX}'::regclass);")
            sizes["partial_index_bytes"] = cur.fetchone()[0]
            sizes["partial_index_pretty"] = format_bytes(sizes["partial_index_bytes"])
        else:
            sizes["partial_index_bytes"] = 0
            sizes["partial_index_pretty"] = "0 bytes"

    if sizes["composite_index_bytes"] > 0 and sizes["partial_index_bytes"] > 0:
        saved_bytes = sizes["composite_index_bytes"] - sizes["partial_index_bytes"]
        pct_savings = (saved_bytes / sizes["composite_index_bytes"]) * 100.0
        sizes["footprint_reduction_bytes"] = saved_bytes
        sizes["footprint_reduction_pretty"] = format_bytes(saved_bytes)
        sizes["footprint_reduction_percent"] = round(pct_savings, 2)

    return sizes


def run_explain_analyze(conn, query: str, session_sql: str = None) -> dict:
    with conn.cursor() as cur:
        if session_sql:
            cur.execute(session_sql)
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
        cur.execute(explain_query)
        res = cur.fetchone()[0]
        plan_info = res[0]

    plan = plan_info.get("Plan", {})
    planning_time = plan_info.get("Planning Time", 0.0)
    execution_time = plan_info.get("Execution Time", 0.0)

    # Extract buffers recursively
    def extract_buffers(node):
        hits = node.get("Shared Hit Blocks", 0)
        reads = node.get("Shared Read Blocks", 0)
        dirtied = node.get("Shared Dirtied Blocks", 0)
        written = node.get("Shared Written Blocks", 0)
        for child in node.get("Plans", []):
            ch, cr, cd, cw = extract_buffers(child)
            hits += ch
            reads += cr
            dirtied += cd
            written += cw
        return hits, reads, dirtied, written

    hits, reads, dirtied, written = extract_buffers(plan)

    # Find root scan node details
    def find_scan_node(node):
        if "Index Name" in node or "Node Type" in node:
            if "Scan" in node.get("Node Type", ""):
                return node
        for child in node.get("Plans", []):
            res_node = find_scan_node(child)
            if res_node:
                return res_node
        return node

    scan_node = find_scan_node(plan)

    return {
        "node_type": plan.get("Node Type"),
        "scan_node_type": scan_node.get("Node Type"),
        "index_name": scan_node.get("Index Name"),
        "planning_time_ms": round(planning_time, 4),
        "execution_time_ms": round(execution_time, 4),
        "shared_hit_blocks": hits,
        "shared_read_blocks": reads,
        "shared_total_blocks": hits + reads,
        "raw_plan": plan_info,
    }


def benchmark_latency(conn, query: str, iterations: int, warmup: int = 10, session_sql: str = None) -> dict:
    with conn.cursor() as cur:
        if session_sql:
            cur.execute(session_sql)

        # Warmup
        for _ in range(warmup):
            cur.execute(query)
            cur.fetchall()

        latencies_ms = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            cur.execute(query)
            cur.fetchall()
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)

    latencies_ms.sort()
    mean_val = statistics.mean(latencies_ms)
    median_val = statistics.median(latencies_ms)
    p95_val = latencies_ms[int(len(latencies_ms) * 0.95)]
    p99_val = latencies_ms[int(len(latencies_ms) * 0.99)]
    min_val = min(latencies_ms)
    max_val = max(latencies_ms)
    stddev_val = statistics.stdev(latencies_ms) if len(latencies_ms) > 1 else 0.0

    return {
        "iterations": iterations,
        "warmup": warmup,
        "min_ms": round(min_val, 4),
        "mean_ms": round(mean_val, 4),
        "median_ms": round(median_val, 4),
        "p95_ms": round(p95_val, 4),
        "p99_ms": round(p99_val, 4),
        "max_ms": round(max_val, 4),
        "stddev_ms": round(stddev_val, 4),
    }


def compute_sha256(filepath: Path) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def update_sha256_manifest(output_dir: Path):
    manifest_path = output_dir / "SHA256SUMS.txt"
    entries = []
    for item in sorted(output_dir.iterdir()):
        if item.is_file() and item.name != "SHA256SUMS.txt":
            checksum = compute_sha256(item)
            entries.append(f"{checksum}  {item.name}")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("\n".join(entries) + "\n")
    print(f"Manifest written to {manifest_path} with {len(entries)} file entries.")


def main():
    print("=" * 70)
    print("PostgreSQL 18 Indexing Optimization Benchmark (Artifact D11)")
    print("=" * 70)

    conn = get_connection(autocommit=True)

    # Verify table row count
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.{TABLE_NAME};")
        total_rows = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.{TABLE_NAME} WHERE status = 'ACTIVE';")
        active_rows = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.{TABLE_NAME} WHERE status != 'ACTIVE';")
        inactive_rows = cur.fetchone()[0]

    print(f"Dataset Size: {total_rows:,} rows")
    print(f"Active Rows:  {active_rows:,} ({active_rows / total_rows * 100:.2f}%)")
    print(f"Inactive:     {inactive_rows:,} ({inactive_rows / total_rows * 100:.2f}%)")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Benchmark 1: Sequential Scan Baseline
    print("\n[Phase 1] Benchmarking Sequential Scan Baseline...")
    seq_session = "SET enable_indexscan = off; SET enable_bitmapscan = off; SET enable_indexonlyscan = off;"
    seq_explain = run_explain_analyze(conn, BENCHMARK_QUERY, session_sql=seq_session)
    print(f"  Explain Plan: {seq_explain['scan_node_type']} (Execution: {seq_explain['execution_time_ms']:.2f} ms, Buffers: {seq_explain['shared_total_blocks']})")
    
    # Run 50 iterations for Sequential Scan
    seq_latencies = benchmark_latency(conn, BENCHMARK_QUERY, iterations=50, warmup=3, session_sql=seq_session)
    print(f"  Client Latency: Mean: {seq_latencies['mean_ms']:.2f} ms, Median: {seq_latencies['median_ms']:.2f} ms, P95: {seq_latencies['p95_ms']:.2f} ms")

    # Reset planner flags
    with conn.cursor() as cur:
        cur.execute("RESET enable_indexscan; RESET enable_bitmapscan; RESET enable_indexonlyscan;")

    # Benchmark 2: Full Composite Index Isolated
    print("\n[Phase 2] Benchmarking Full Composite Index...")
    with conn.cursor() as cur:
        cur.execute(f"DROP INDEX IF EXISTS {SCHEMA_NAME}.{PARTIAL_INDEX};")
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS {COMPOSITE_INDEX}
            ON {SCHEMA_NAME}.{TABLE_NAME} (status, created_at DESC);
        """)
        cur.execute(f"ANALYZE {SCHEMA_NAME}.{TABLE_NAME};")

    composite_explain = run_explain_analyze(conn, BENCHMARK_QUERY)
    print(f"  Explain Plan: {composite_explain['scan_node_type']} using {composite_explain['index_name']} (Execution: {composite_explain['execution_time_ms']:.4f} ms, Buffers: {composite_explain['shared_total_blocks']})")

    # Run 1,000 iterations for Composite Index
    composite_latencies = benchmark_latency(conn, BENCHMARK_QUERY, iterations=1000, warmup=20)
    print(f"  Client Latency (1,000 runs): Mean: {composite_latencies['mean_ms']:.4f} ms, Median: {composite_latencies['median_ms']:.4f} ms, P95: {composite_latencies['p95_ms']:.4f} ms")

    # Benchmark 3: Optimized Partial Index Isolated
    print("\n[Phase 3] Benchmarking Optimized Partial Index...")
    with conn.cursor() as cur:
        cur.execute(f"DROP INDEX IF EXISTS {SCHEMA_NAME}.{COMPOSITE_INDEX};")
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS {PARTIAL_INDEX}
            ON {SCHEMA_NAME}.{TABLE_NAME} (created_at DESC)
            WHERE status = 'ACTIVE';
        """)
        cur.execute(f"ANALYZE {SCHEMA_NAME}.{TABLE_NAME};")

    partial_explain = run_explain_analyze(conn, BENCHMARK_QUERY)
    print(f"  Explain Plan: {partial_explain['scan_node_type']} using {partial_explain['index_name']} (Execution: {partial_explain['execution_time_ms']:.4f} ms, Buffers: {partial_explain['shared_total_blocks']})")

    # Run 1,000 iterations for Partial Index
    partial_latencies = benchmark_latency(conn, BENCHMARK_QUERY, iterations=1000, warmup=20)
    print(f"  Client Latency (1,000 runs): Mean: {partial_latencies['mean_ms']:.4f} ms, Median: {partial_latencies['median_ms']:.4f} ms, P95: {partial_latencies['p95_ms']:.4f} ms")

    # Benchmark 4: Recreate Both Indexes for Coexistence & Final Size Measurement
    print("\n[Phase 4] Rebuilding Both Indexes for Footprint Comparison...")
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS {COMPOSITE_INDEX}
            ON {SCHEMA_NAME}.{TABLE_NAME} (status, created_at DESC);
        """)
        cur.execute(f"ANALYZE {SCHEMA_NAME}.{TABLE_NAME};")

    sizes = get_relation_sizes(conn)
    print(f"  Table Size:           {sizes['table_pretty']} ({sizes['table_bytes']:,} bytes)")
    print(f"  Composite Index Size: {sizes['composite_index_pretty']} ({sizes['composite_index_bytes']:,} bytes)")
    print(f"  Partial Index Size:   {sizes['partial_index_pretty']} ({sizes['partial_index_bytes']:,} bytes)")
    print(f"  Footprint Reduction:  {sizes['footprint_reduction_pretty']} ({sizes['footprint_reduction_percent']}%)")

    # Compute Speedup Factors
    seq_mean = seq_latencies["mean_ms"]
    comp_mean = composite_latencies["mean_ms"]
    part_mean = partial_latencies["mean_ms"]

    composite_speedup = round(seq_mean / comp_mean, 2) if comp_mean > 0 else 0.0
    partial_speedup = round(seq_mean / part_mean, 2) if part_mean > 0 else 0.0

    seq_server_exec = seq_explain["execution_time_ms"]
    comp_server_exec = composite_explain["execution_time_ms"]
    part_server_exec = partial_explain["execution_time_ms"]

    server_composite_speedup = round(seq_server_exec / comp_server_exec, 2) if comp_server_exec > 0 else 0.0
    server_partial_speedup = round(seq_server_exec / part_server_exec, 2) if part_server_exec > 0 else 0.0

    buffer_reduction_pct = round(((seq_explain["shared_total_blocks"] - partial_explain["shared_total_blocks"]) / seq_explain["shared_total_blocks"]) * 100.0, 2)

    metrics_payload = {
        "artifact_id": "D11",
        "round": "R1",
        "service": "PostgreSQL Composite Indexing and Partial Index Setup",
        "database_version": "PostgreSQL 18.0",
        "port": DB_PORT,
        "schema": SCHEMA_NAME,
        "table": TABLE_NAME,
        "timestamp_epoch": time.time(),
        "dataset": {
            "total_rows": total_rows,
            "active_rows": active_rows,
            "inactive_rows": inactive_rows,
            "active_percentage": round((active_rows / total_rows) * 100.0, 2),
        },
        "query": BENCHMARK_QUERY.strip(),
        "storage": {
            "table_bytes": sizes["table_bytes"],
            "table_pretty": sizes["table_pretty"],
            "total_relation_bytes": sizes["total_relation_bytes"],
            "total_relation_pretty": sizes["total_relation_pretty"],
            "composite_index_bytes": sizes["composite_index_bytes"],
            "composite_index_pretty": sizes["composite_index_pretty"],
            "partial_index_bytes": sizes["partial_index_bytes"],
            "partial_index_pretty": sizes["partial_index_pretty"],
            "footprint_reduction_bytes": sizes["footprint_reduction_bytes"],
            "footprint_reduction_pretty": sizes["footprint_reduction_pretty"],
            "footprint_reduction_percent": sizes["footprint_reduction_percent"],
            "acceptance_criteria_passed_75pct_threshold": sizes["footprint_reduction_percent"] >= 75.0,
        },
        "benchmarks": {
            "sequential_scan": {
                "scan_type": seq_explain["scan_node_type"],
                "server_explain": {
                    "planning_time_ms": seq_explain["planning_time_ms"],
                    "execution_time_ms": seq_explain["execution_time_ms"],
                    "shared_hit_blocks": seq_explain["shared_hit_blocks"],
                    "shared_read_blocks": seq_explain["shared_read_blocks"],
                    "shared_total_blocks": seq_explain["shared_total_blocks"],
                },
                "client_latencies": seq_latencies,
            },
            "composite_index": {
                "index_name": COMPOSITE_INDEX,
                "scan_type": composite_explain["scan_node_type"],
                "server_explain": {
                    "planning_time_ms": composite_explain["planning_time_ms"],
                    "execution_time_ms": composite_explain["execution_time_ms"],
                    "shared_hit_blocks": composite_explain["shared_hit_blocks"],
                    "shared_read_blocks": composite_explain["shared_read_blocks"],
                    "shared_total_blocks": composite_explain["shared_total_blocks"],
                },
                "client_latencies": composite_latencies,
                "server_speedup_vs_seq_scan": server_composite_speedup,
                "client_speedup_vs_seq_scan": composite_speedup,
            },
            "partial_index": {
                "index_name": PARTIAL_INDEX,
                "scan_type": partial_explain["scan_node_type"],
                "server_explain": {
                    "planning_time_ms": partial_explain["planning_time_ms"],
                    "execution_time_ms": partial_explain["execution_time_ms"],
                    "shared_hit_blocks": partial_explain["shared_hit_blocks"],
                    "shared_read_blocks": partial_explain["shared_read_blocks"],
                    "shared_total_blocks": partial_explain["shared_total_blocks"],
                },
                "client_latencies": partial_latencies,
                "server_speedup_vs_seq_scan": server_partial_speedup,
                "client_speedup_vs_seq_scan": partial_speedup,
            },
        },
        "optimizations_summary": {
            "query_latency_sequential_ms": seq_explain["execution_time_ms"],
            "query_latency_partial_index_ms": partial_explain["execution_time_ms"],
            "sub_millisecond_achieved": partial_explain["execution_time_ms"] < 1.0,
            "shared_buffer_reduction_percent": buffer_reduction_pct,
            "storage_reduction_percent": sizes["footprint_reduction_percent"],
        },
    }

    # Save metrics JSON
    metrics_path = OUTPUT_DIR / "index_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)
    print(f"\nSaved metrics to {metrics_path}")

    # Generate SHA-256 manifest
    update_sha256_manifest(OUTPUT_DIR)

    conn.close()

    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY RESULTS")
    print("=" * 70)
    print(f"Sequential Scan Execution Time:    {seq_explain['execution_time_ms']:.2f} ms ({seq_explain['shared_total_blocks']} shared buffers)")
    print(f"Partial Index Execution Time:      {partial_explain['execution_time_ms']:.4f} ms ({partial_explain['shared_total_blocks']} shared buffers)")
    print(f"Server Execution Speedup Factor:   {server_partial_speedup:.1f}x")
    print(f"Buffer Read Reduction:             {buffer_reduction_pct:.2f}%")
    print(f"Composite Index Size:              {sizes['composite_index_pretty']}")
    print(f"Partial Index Size:                {sizes['partial_index_pretty']}")
    print(f"Disk Storage Reduction:            {sizes['footprint_reduction_percent']:.2f}% (Required: >= 75%)")
    print("=" * 70)


if __name__ == "__main__":
    main()
