"""
Streaming Postgres COPY Ingestion Pipeline for Artifact D12.
Streams 500,000 rows directly from disk buffer to PostgreSQL 18 socket.
Monitors throughput, execution time, and process RSS memory footprint.
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
TABLE_NAME = "inventory"
CSV_PATH = "inventory_500k.csv"
OUTPUT_DIR = "output"
METRICS_PATH = os.path.join(OUTPUT_DIR, "ingestion_metrics.json")


class StreamingSocketBuffer(TextIOBase):
    """
    In-memory streaming buffer adapter wrapping file stream.
    Streams chunks directly from disk to psycopg2 libpq copy buffer,
    tracking peak RSS memory and bytes streamed without buffering full dataset.
    """

    def __init__(self, file_path: str, chunk_size: int = 65536):
        super().__init__()
        self.file_path = file_path
        self.chunk_size = chunk_size
        self._file = None
        self.bytes_streamed = 0
        self.reads_count = 0
        self.process = psutil.Process()
        self.peak_rss_bytes = self.process.memory_info().rss

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
            self.reads_count += 1
            # Sample memory every 50 chunks
            if self.reads_count % 50 == 0:
                current_rss = self.process.memory_info().rss
                if current_rss > self.peak_rss_bytes:
                    self.peak_rss_bytes = current_rss
        else:
            current_rss = self.process.memory_info().rss
            if current_rss > self.peak_rss_bytes:
                self.peak_rss_bytes = current_rss
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


def reset_table(conn):
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};")
        cur.execute(f"TRUNCATE TABLE {SCHEMA_NAME}.{TABLE_NAME};")
    conn.commit()


def run_streaming_copy(csv_path: str = CSV_PATH) -> dict:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Input file not found: {csv_path}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    process = psutil.Process()
    initial_rss_mb = process.memory_info().rss / (1024 * 1024)

    conn = get_connection()
    try:
        reset_table(conn)
        print(f"Connecting to PostgreSQL 18 ({DB_HOST}:{DB_PORT}/{DB_NAME})...")
        print(f"Executing streaming COPY into {SCHEMA_NAME}.{TABLE_NAME}...")

        start_time = time.perf_counter()

        with conn.cursor() as cur:
            with StreamingSocketBuffer(csv_path) as stream_buffer:
                copy_sql = f"COPY {SCHEMA_NAME}.{TABLE_NAME} FROM STDIN WITH CSV HEADER"
                cur.copy_expert(copy_sql, stream_buffer)
                peak_rss_during_copy_mb = stream_buffer.peak_rss_bytes / (1024 * 1024)
                total_bytes_streamed = stream_buffer.bytes_streamed

        # Commit transaction
        commit_start = time.perf_counter()
        conn.commit()
        commit_time = time.perf_counter() - commit_start

        total_elapsed = time.perf_counter() - start_time
        final_rss_mb = process.memory_info().rss / (1024 * 1024)
        peak_rss_mb = max(initial_rss_mb, peak_rss_during_copy_mb, final_rss_mb)

        # Verify row count
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.{TABLE_NAME};")
            verified_row_count = cur.fetchone()[0]

        rows_per_second = verified_row_count / total_elapsed if total_elapsed > 0 else 0
        mb_per_second = (total_bytes_streamed / (1024 * 1024)) / total_elapsed if total_elapsed > 0 else 0

        print(f"Ingestion completed in {total_elapsed:.3f}s (commit: {commit_time:.3f}s)")
        print(f"Rows loaded: {verified_row_count:,}")
        print(f"Throughput: {rows_per_second:,.2f} rows/sec ({mb_per_second:.2f} MB/sec)")
        print(f"Host memory footprint: Initial={initial_rss_mb:.2f}MB, Peak={peak_rss_mb:.2f}MB, Final={final_rss_mb:.2f}MB")

        metrics = {
            "task_id": "t_e89c9163",
            "artifact_id": "D12",
            "round": "R1",
            "database": {
                "engine": "PostgreSQL",
                "port": DB_PORT,
                "schema": SCHEMA_NAME,
                "table": TABLE_NAME,
            },
            "dataset": {
                "file": csv_path,
                "file_size_bytes": total_bytes_streamed,
                "file_size_mb": round(total_bytes_streamed / (1024 * 1024), 2),
                "verified_row_count": verified_row_count,
            },
            "performance": {
                "total_elapsed_seconds": round(total_elapsed, 4),
                "commit_elapsed_seconds": round(commit_time, 4),
                "rows_per_second": round(rows_per_second, 2),
                "mb_per_second": round(mb_per_second, 2),
                "target_max_seconds": 5.0,
                "target_min_rows_per_sec": 100000.0,
                "timing_gate_passed": total_elapsed < 5.0,
            },
            "memory": {
                "initial_rss_mb": round(initial_rss_mb, 2),
                "peak_rss_mb": round(peak_rss_mb, 2),
                "final_rss_mb": round(final_rss_mb, 2),
                "target_max_rss_mb": 35.0,
                "memory_gate_passed": peak_rss_mb <= 35.0,
            },
            "acceptance_criteria_verified": (
                verified_row_count == 500000
                and total_elapsed < 5.0
                and peak_rss_mb <= 35.0
            ),
        }

        with open(METRICS_PATH, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        print(f"Saved metrics to {METRICS_PATH}")
        return metrics

    finally:
        conn.close()


if __name__ == "__main__":
    run_streaming_copy()
