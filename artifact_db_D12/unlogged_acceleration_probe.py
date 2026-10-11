"""
Unlogged Table Acceleration Benchmark Probe for Artifact D12 Round 2.
Compares PostgreSQL WAL disk write volume and ingestion throughput
between standard LOGGED tables versus UNLOGGED staging tables followed by ALTER TABLE SET LOGGED.
Strict zero em dash policy enforced.
"""

import os
import sys
import time
import json
import psutil
import psycopg2
from io import TextIOBase

DB_HOST = os.getenv("PGHOST", "127.0.0.1")
DB_PORT = int(os.getenv("PGPORT", "5433"))
DB_NAME = os.getenv("PGDATABASE", "postgres")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
SCHEMA_NAME = "d12_copy_sandbox"
TABLE_LOGGED = "bench_inventory_logged"
TABLE_UNLOGGED = "bench_inventory_unlogged"
CSV_PATH = "inventory_500k.csv"
OUTPUT_DIR = "output"
METRICS_PATH = os.path.join(OUTPUT_DIR, "unlogged_bench_metrics.json")


class StreamingSocketBuffer(TextIOBase):
    def __init__(self, file_path: str, chunk_size: int = 65536):
        super().__init__()
        self.file_path = file_path
        self.chunk_size = chunk_size
        self._file = None
        self.bytes_streamed = 0

    def __enter__(self):
        self._file = open(self.file_path, "r", encoding="utf-8", buffering=self.chunk_size)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()

    def read(self, size: int = -1) -> str:
        read_size = self.chunk_size if size is None or size < 0 else size
        data = self._file.read(read_size)
        if data:
            self.bytes_streamed += len(data.encode("utf-8"))
        return data

    def readable(self) -> bool:
        return True


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def get_current_wal_lsn(conn) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_current_wal_lsn()::text;")
        return cur.fetchone()[0]


def get_wal_difference_bytes(conn, start_lsn: str, end_lsn: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_wal_lsn_diff(%s, %s);", (end_lsn, start_lsn))
        return int(cur.fetchone()[0])


def run_unlogged_benchmark(csv_path: str = CSV_PATH) -> dict:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found: {csv_path}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    conn = get_connection()

    try:
        # Step 1: Benchmark standard LOGGED table ingestion
        print(f"Preparing standard LOGGED table {SCHEMA_NAME}.{TABLE_LOGGED}...")
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};")
            cur.execute(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.{TABLE_LOGGED};")
            cur.execute(f"""
                CREATE TABLE {SCHEMA_NAME}.{TABLE_LOGGED} (
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

        # Measure LOGGED ingestion
        start_wal_logged = get_current_wal_lsn(conn)
        logged_start_time = time.perf_counter()

        with conn.cursor() as cur:
            with StreamingSocketBuffer(csv_path) as stream_buffer:
                copy_sql = f"COPY {SCHEMA_NAME}.{TABLE_LOGGED} FROM STDIN WITH CSV HEADER"
                cur.copy_expert(copy_sql, stream_buffer)
        conn.commit()

        logged_elapsed = time.perf_counter() - logged_start_time
        end_wal_logged = get_current_wal_lsn(conn)
        logged_wal_bytes = get_wal_difference_bytes(conn, start_wal_logged, end_wal_logged)

        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.{TABLE_LOGGED};")
            logged_count = cur.fetchone()[0]

        logged_rows_per_sec = logged_count / logged_elapsed if logged_elapsed > 0 else 0
        logged_wal_mb = logged_wal_bytes / (1024 * 1024)

        print(f"Logged table ingestion completed:")
        print(f"  Rows loaded: {logged_count:,}")
        print(f"  Duration: {logged_elapsed:.4f}s ({logged_rows_per_sec:,.2f} rows/sec)")
        print(f"  WAL bytes generated: {logged_wal_bytes:,} ({logged_wal_mb:.2f} MB)")

        # Step 2: Benchmark UNLOGGED table ingestion + ALTER TABLE SET LOGGED
        print(f"\nPreparing UNLOGGED staging table {SCHEMA_NAME}.{TABLE_UNLOGGED}...")
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.{TABLE_UNLOGGED};")
            cur.execute(f"""
                CREATE UNLOGGED TABLE {SCHEMA_NAME}.{TABLE_UNLOGGED} (
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

        # Measure UNLOGGED COPY phase
        start_wal_unlogged = get_current_wal_lsn(conn)
        unlogged_copy_start = time.perf_counter()

        with conn.cursor() as cur:
            with StreamingSocketBuffer(csv_path) as stream_buffer:
                copy_sql = f"COPY {SCHEMA_NAME}.{TABLE_UNLOGGED} FROM STDIN WITH CSV HEADER"
                cur.copy_expert(copy_sql, stream_buffer)
        conn.commit()

        unlogged_copy_elapsed = time.perf_counter() - unlogged_copy_start
        mid_wal_unlogged = get_current_wal_lsn(conn)
        unlogged_copy_wal_bytes = get_wal_difference_bytes(conn, start_wal_unlogged, mid_wal_unlogged)

        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.{TABLE_UNLOGGED};")
            unlogged_count = cur.fetchone()[0]

        unlogged_rows_per_sec = unlogged_count / unlogged_copy_elapsed if unlogged_copy_elapsed > 0 else 0
        unlogged_copy_wal_mb = unlogged_copy_wal_bytes / (1024 * 1024)

        print(f"Unlogged staging table ingestion completed:")
        print(f"  Rows loaded: {unlogged_count:,}")
        print(f"  Duration: {unlogged_copy_elapsed:.4f}s ({unlogged_rows_per_sec:,.2f} rows/sec)")
        print(f"  WAL bytes generated during COPY: {unlogged_copy_wal_bytes:,} ({unlogged_copy_wal_mb:.4f} MB)")

        # Measure ALTER TABLE SET LOGGED phase
        print("Executing ALTER TABLE SET LOGGED transition...")
        alter_start_time = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute(f"ALTER TABLE {SCHEMA_NAME}.{TABLE_UNLOGGED} SET LOGGED;")
        conn.commit()
        alter_elapsed = time.perf_counter() - alter_start_time

        end_wal_unlogged = get_current_wal_lsn(conn)
        alter_wal_bytes = get_wal_difference_bytes(conn, mid_wal_unlogged, end_wal_unlogged)
        total_unlogged_pipeline_wal_bytes = get_wal_difference_bytes(conn, start_wal_unlogged, end_wal_unlogged)
        total_unlogged_pipeline_seconds = unlogged_copy_elapsed + alter_elapsed

        # Comparative analysis
        wal_savings_copy_bytes = max(0, logged_wal_bytes - unlogged_copy_wal_bytes)
        wal_savings_copy_pct = (wal_savings_copy_bytes / logged_wal_bytes * 100.0) if logged_wal_bytes > 0 else 0.0
        copy_speedup_factor = unlogged_rows_per_sec / logged_rows_per_sec if logged_rows_per_sec > 0 else 0.0

        print(f"\nUnlogged Acceleration Results:")
        print(f"  Ingestion speedup factor: {copy_speedup_factor:.2f}x ({unlogged_rows_per_sec:,.2f} vs {logged_rows_per_sec:,.2f} rows/sec)")
        print(f"  WAL saved during ingestion: {wal_savings_copy_bytes:,} bytes ({wal_savings_copy_bytes / (1024 * 1024):.2f} MB, {wal_savings_copy_pct:.2f}% reduction)")
        print(f"  ALTER TABLE SET LOGGED duration: {alter_elapsed:.4f}s")
        print(f"  Total unlogged pipeline duration: {total_unlogged_pipeline_seconds:.4f}s")

        # Clean up temporary benchmark tables
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.{TABLE_LOGGED};")
            cur.execute(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.{TABLE_UNLOGGED};")
        conn.commit()

        metrics = {
            "probe_name": "Unlogged Table Acceleration Benchmark",
            "task_id": "t_7abdcdec",
            "artifact_id": "D12",
            "round": "R2",
            "dataset": {
                "file": csv_path,
                "total_rows": logged_count,
            },
            "logged_table_benchmark": {
                "elapsed_seconds": round(logged_elapsed, 4),
                "throughput_rows_per_sec": round(logged_rows_per_sec, 2),
                "wal_bytes_generated": logged_wal_bytes,
                "wal_mb_generated": round(logged_wal_mb, 2),
                "start_lsn": start_wal_logged,
                "end_lsn": end_wal_logged,
            },
            "unlogged_table_benchmark": {
                "copy_phase_seconds": round(unlogged_copy_elapsed, 4),
                "copy_throughput_rows_per_sec": round(unlogged_rows_per_sec, 2),
                "copy_wal_bytes_generated": unlogged_copy_wal_bytes,
                "copy_wal_mb_generated": round(unlogged_copy_wal_mb, 4),
                "alter_logged_phase_seconds": round(alter_elapsed, 4),
                "alter_logged_wal_bytes": alter_wal_bytes,
                "total_pipeline_seconds": round(total_unlogged_pipeline_seconds, 4),
                "total_wal_bytes": total_unlogged_pipeline_wal_bytes,
                "start_lsn": start_wal_unlogged,
                "mid_lsn": mid_wal_unlogged,
                "end_lsn": end_wal_unlogged,
            },
            "acceleration_summary": {
                "copy_throughput_speedup": f"{copy_speedup_factor:.2f}x",
                "wal_disk_bytes_saved_during_copy": wal_savings_copy_bytes,
                "wal_disk_mb_saved_during_copy": round(wal_savings_copy_bytes / (1024 * 1024), 2),
                "wal_savings_percentage_during_copy": f"{wal_savings_copy_pct:.2f}%",
                "recommendation": "For high-volume bulk ingestion batches exceeding 100k rows, stream into an UNLOGGED staging table to eliminate client transaction WAL write stalls, then perform SET LOGGED or promotion to target tables."
            },
            "acceptance_criteria_verified": (
                logged_count == 500000
                and unlogged_count == 500000
                and unlogged_copy_wal_bytes < logged_wal_bytes
            ),
        }

        with open(METRICS_PATH, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        print(f"Benchmark metrics saved to {METRICS_PATH}")
        return metrics

    finally:
        conn.close()


if __name__ == "__main__":
    run_unlogged_benchmark()
