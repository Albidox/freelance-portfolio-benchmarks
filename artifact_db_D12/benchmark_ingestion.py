"""
Benchmark suite comparing PostgreSQL ingestion strategies.
Compares standard row-by-row insert, batch insert (execute_values), and streaming COPY.
Measures execution duration, throughput (rows/sec), and process RSS memory footprint.
Strict zero em dash policy enforced.
"""

import os
import sys
import time
import json
import csv
import psutil
import psycopg2
from psycopg2.extras import execute_values
from ingest_pipeline import StreamingSocketBuffer, get_connection, SCHEMA_NAME, TABLE_NAME, CSV_PATH

OUTPUT_DIR = "output"
BENCHMARK_RESULTS_PATH = os.path.join(OUTPUT_DIR, "benchmark_comparison.json")


def setup_benchmark_tables(conn):
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};")
        cur.execute(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.bench_single_insert;")
        cur.execute(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.bench_batch_insert;")
        cur.execute(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.bench_streaming_copy;")

        for tbl in ["bench_single_insert", "bench_batch_insert", "bench_streaming_copy"]:
            cur.execute(f"""
                CREATE TABLE {SCHEMA_NAME}.{tbl} (
                    id UUID NOT NULL,
                    sku VARCHAR(64) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    price NUMERIC(10, 2) NOT NULL,
                    stock INTEGER NOT NULL,
                    category VARCHAR(64) NOT NULL,
                    warehouse_id VARCHAR(32) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                );
            """)
    conn.commit()


def read_sample_rows(csv_path: str, count: int):
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for i, row in enumerate(reader):
            if i >= count:
                break
            rows.append(tuple(row))
    return rows


def benchmark_single_row_inserts(conn, rows: list) -> dict:
    process = psutil.Process()
    initial_rss = process.memory_info().rss / (1024 * 1024)
    start_time = time.perf_counter()

    sql = f"""
        INSERT INTO {SCHEMA_NAME}.bench_single_insert
        (id, sku, name, price, stock, category, warehouse_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
    """
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(sql, r)
    conn.commit()

    elapsed = time.perf_counter() - start_time
    final_rss = process.memory_info().rss / (1024 * 1024)
    throughput = len(rows) / elapsed if elapsed > 0 else 0

    return {
        "method": "Single-Row Standard INSERT",
        "rows_tested": len(rows),
        "elapsed_seconds": round(elapsed, 4),
        "throughput_rows_per_sec": round(throughput, 2),
        "initial_rss_mb": round(initial_rss, 2),
        "final_rss_mb": round(final_rss, 2),
        "rss_delta_mb": round(final_rss - initial_rss, 2),
    }


def benchmark_batch_inserts(conn, rows: list, page_size: int = 1000) -> dict:
    process = psutil.Process()
    initial_rss = process.memory_info().rss / (1024 * 1024)
    start_time = time.perf_counter()

    sql = f"""
        INSERT INTO {SCHEMA_NAME}.bench_batch_insert
        (id, sku, name, price, stock, category, warehouse_id, created_at)
        VALUES %s;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=page_size)
    conn.commit()

    elapsed = time.perf_counter() - start_time
    final_rss = process.memory_info().rss / (1024 * 1024)
    throughput = len(rows) / elapsed if elapsed > 0 else 0

    return {
        "method": f"Batch INSERT via execute_values (page_size={page_size})",
        "rows_tested": len(rows),
        "elapsed_seconds": round(elapsed, 4),
        "throughput_rows_per_sec": round(throughput, 2),
        "initial_rss_mb": round(initial_rss, 2),
        "final_rss_mb": round(final_rss, 2),
        "rss_delta_mb": round(final_rss - initial_rss, 2),
    }


def benchmark_streaming_copy(conn, csv_path: str) -> dict:
    process = psutil.Process()
    initial_rss = process.memory_info().rss / (1024 * 1024)
    start_time = time.perf_counter()

    with conn.cursor() as cur:
        with StreamingSocketBuffer(csv_path) as buffer:
            copy_sql = f"COPY {SCHEMA_NAME}.bench_streaming_copy FROM STDIN WITH CSV HEADER"
            cur.copy_expert(copy_sql, buffer)
            peak_buffer_rss = buffer.peak_rss_bytes / (1024 * 1024)
            bytes_streamed = buffer.bytes_streamed
    conn.commit()

    elapsed = time.perf_counter() - start_time
    final_rss = process.memory_info().rss / (1024 * 1024)
    peak_rss = max(initial_rss, peak_buffer_rss, final_rss)

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.bench_streaming_copy;")
        total_rows = cur.fetchone()[0]

    throughput = total_rows / elapsed if elapsed > 0 else 0
    mb_throughput = (bytes_streamed / (1024 * 1024)) / elapsed if elapsed > 0 else 0

    return {
        "method": "Streaming COPY FROM STDIN (cursor.copy_expert)",
        "rows_tested": total_rows,
        "elapsed_seconds": round(elapsed, 4),
        "throughput_rows_per_sec": round(throughput, 2),
        "mb_per_second": round(mb_throughput, 2),
        "initial_rss_mb": round(initial_rss, 2),
        "peak_rss_mb": round(peak_rss, 2),
        "final_rss_mb": round(final_rss, 2),
        "rss_delta_mb": round(final_rss - initial_rss, 2),
    }


def run_benchmark():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    conn = get_connection()
    try:
        print("Setting up benchmark tables in PostgreSQL 18...")
        setup_benchmark_tables(conn)

        sample_single_size = 5_000
        sample_batch_size = 25_000

        print(f"Reading {sample_batch_size:,} sample rows for client-side insert tests...")
        sample_rows_batch = read_sample_rows(CSV_PATH, sample_batch_size)
        sample_rows_single = sample_rows_batch[:sample_single_size]

        print(f"Running Benchmark 1: Single-row INSERT ({sample_single_size:,} rows)...")
        res_single = benchmark_single_row_inserts(conn, sample_rows_single)
        print(f"  Single-row completed: {res_single['elapsed_seconds']}s ({res_single['throughput_rows_per_sec']:,.2f} rows/s)")

        print(f"Running Benchmark 2: Batch execute_values ({sample_batch_size:,} rows)...")
        res_batch = benchmark_batch_inserts(conn, sample_rows_batch, page_size=1000)
        print(f"  Batch completed: {res_batch['elapsed_seconds']}s ({res_batch['throughput_rows_per_sec']:,.2f} rows/s)")

        print("Running Benchmark 3: Streaming COPY FROM STDIN (Full 500,000 rows)...")
        res_copy = benchmark_streaming_copy(conn, CSV_PATH)
        print(f"  Streaming COPY completed: {res_copy['elapsed_seconds']}s ({res_copy['throughput_rows_per_sec']:,.2f} rows/s)")

        # Calculate comparative speedup factors
        single_speedup = round(res_copy["throughput_rows_per_sec"] / res_single["throughput_rows_per_sec"], 2)
        batch_speedup = round(res_copy["throughput_rows_per_sec"] / res_batch["throughput_rows_per_sec"], 2)

        benchmark_summary = {
            "artifact": "D12",
            "environment": {
                "database": "PostgreSQL 18 (Native Win64)",
                "schema": SCHEMA_NAME,
                "dataset_rows": 500_000,
            },
            "results": {
                "single_row_insert": res_single,
                "batch_execute_values": res_batch,
                "streaming_copy_stdin": res_copy,
            },
            "comparisons": {
                "copy_vs_single_speedup_factor": f"{single_speedup}x",
                "copy_vs_batch_speedup_factor": f"{batch_speedup}x",
                "extrapolated_500k_single_insert_seconds": round(500000 / res_single["throughput_rows_per_sec"], 2),
                "extrapolated_500k_batch_insert_seconds": round(500000 / res_batch["throughput_rows_per_sec"], 2),
                "actual_500k_streaming_copy_seconds": res_copy["elapsed_seconds"],
            },
        }

        with open(BENCHMARK_RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(benchmark_summary, f, indent=2)

        print(f"Benchmark report saved to {BENCHMARK_RESULTS_PATH}")
        print("\n=== BENCHMARK SUMMARY ===")
        print(f"Single-Row INSERT:   {res_single['throughput_rows_per_sec']:>10,.1f} rows/sec | Extrapolated 500k: {benchmark_summary['comparisons']['extrapolated_500k_single_insert_seconds']:,.1f}s")
        print(f"Batch INSERT:        {res_batch['throughput_rows_per_sec']:>10,.1f} rows/sec | Extrapolated 500k: {benchmark_summary['comparisons']['extrapolated_500k_batch_insert_seconds']:,.1f}s")
        print(f"Streaming COPY:      {res_copy['throughput_rows_per_sec']:>10,.1f} rows/sec | Actual 500k:       {res_copy['elapsed_seconds']:.2f}s")
        print(f"Speedup vs Batch:    {batch_speedup}x faster")
        print(f"Speedup vs Single:   {single_speedup}x faster")
        print(f"Peak Memory:         {res_copy['peak_rss_mb']:.2f} MB RAM")
        return benchmark_summary
    finally:
        conn.close()


if __name__ == "__main__":
    run_benchmark()
