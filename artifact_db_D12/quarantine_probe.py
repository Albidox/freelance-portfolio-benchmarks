"""
Dirty Row Quarantine Probe for Artifact D12 Round 2.
Implements staging-table atomic validation to isolate malformed rows
into quarantined_rows.csv while loading 499,999 valid rows without aborting the batch.
Strict zero em dash policy enforced.
"""

import os
import sys
import time
import json
import csv
import psutil
import psycopg2
from io import TextIOBase

DB_HOST = os.getenv("PGHOST", "127.0.0.1")
DB_PORT = int(os.getenv("PGPORT", "5433"))
DB_NAME = os.getenv("PGDATABASE", "postgres")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
SCHEMA_NAME = "d12_copy_sandbox"
TABLE_TARGET = "inventory"
TABLE_STAGING = "inventory_staging"
TABLE_QUARANTINE = "inventory_quarantine"
DIRTY_CSV_PATH = "inventory_500k_dirty.csv"
OUTPUT_DIR = "output"
QUARANTINE_CSV_OUTPUT = os.path.join(OUTPUT_DIR, "quarantined_rows.csv")
QUARANTINE_CSV_ROOT = "quarantined_rows.csv"
METRICS_PATH = os.path.join(OUTPUT_DIR, "quarantine_metrics.json")


class StreamingSocketBuffer(TextIOBase):
    """
    Streaming buffer adapter wrapping file stream.
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


def setup_quarantine_tables(conn):
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};")

        # Staging table with unconstrained text columns to accept high-speed streaming COPY
        cur.execute(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.{TABLE_STAGING};")
        cur.execute(f"""
            CREATE UNLOGGED TABLE {SCHEMA_NAME}.{TABLE_STAGING} (
                id TEXT,
                sku TEXT,
                name TEXT,
                price TEXT,
                stock TEXT,
                category TEXT,
                warehouse_id TEXT,
                created_at TEXT
            );
        """)

        # Quarantine table for storing isolated malformed records
        cur.execute(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.{TABLE_QUARANTINE};")
        cur.execute(f"""
            CREATE TABLE {SCHEMA_NAME}.{TABLE_QUARANTINE} (
                id TEXT,
                sku TEXT,
                name TEXT,
                price TEXT,
                stock TEXT,
                category TEXT,
                warehouse_id TEXT,
                created_at TEXT,
                quarantine_reason TEXT,
                quarantined_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Target typed inventory table
        cur.execute(f"CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.{TABLE_TARGET} ("
                    f"id UUID NOT NULL, "
                    f"sku VARCHAR(64) NOT NULL, "
                    f"name VARCHAR(255) NOT NULL, "
                    f"price NUMERIC(10, 2) NOT NULL, "
                    f"stock INTEGER NOT NULL, "
                    f"category VARCHAR(64) NOT NULL, "
                    f"warehouse_id VARCHAR(32) NOT NULL, "
                    f"created_at TIMESTAMPTZ NOT NULL);")
        cur.execute(f"TRUNCATE TABLE {SCHEMA_NAME}.{TABLE_TARGET};")

    conn.commit()


def run_quarantine_probe(csv_path: str = DIRTY_CSV_PATH) -> dict:
    if not os.path.exists(csv_path):
        from generate_corrupted_dataset import generate_dirty_dataset
        generate_dirty_dataset()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    process = psutil.Process()
    initial_rss_mb = process.memory_info().rss / (1024 * 1024)

    conn = get_connection()
    try:
        print("Setting up staging and quarantine tables...")
        setup_quarantine_tables(conn)

        print(f"Streaming COPY into unconstrained staging table {SCHEMA_NAME}.{TABLE_STAGING}...")
        stage_start = time.perf_counter()
        with conn.cursor() as cur:
            with StreamingSocketBuffer(csv_path) as stream_buffer:
                copy_sql = f"COPY {SCHEMA_NAME}.{TABLE_STAGING} FROM STDIN WITH CSV HEADER"
                cur.copy_expert(copy_sql, stream_buffer)
                peak_rss_during_copy_mb = stream_buffer.peak_rss_bytes / (1024 * 1024)
                total_bytes_streamed = stream_buffer.bytes_streamed
        conn.commit()
        stage_elapsed = time.perf_counter() - stage_start

        # Verify staging row count
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.{TABLE_STAGING};")
            staging_count = cur.fetchone()[0]
        print(f"Loaded {staging_count:,} rows into staging in {stage_elapsed:.3f}s.")

        print("Executing atomic SQL validation and quarantine separation...")
        validation_start = time.perf_counter()
        with conn.cursor() as cur:
            # 1. Isolate malformed rows into quarantine table
            cur.execute(f"""
                INSERT INTO {SCHEMA_NAME}.{TABLE_QUARANTINE} (
                    id, sku, name, price, stock, category, warehouse_id, created_at, quarantine_reason
                )
                SELECT
                    id, sku, name, price, stock, category, warehouse_id, created_at,
                    CASE
                        WHEN id !~* '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$'
                             AND price !~ '^[0-9]+(\\.[0-9]{{1,2}})?$'
                            THEN 'INVALID_UUID_AND_INVALID_PRICE'
                        WHEN id !~* '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$'
                            THEN 'INVALID_UUID_FORMAT'
                        WHEN price !~ '^[0-9]+(\\.[0-9]{{1,2}})?$'
                            THEN 'INVALID_NUMERIC_PRICE'
                        ELSE 'GENERIC_VALIDATION_ERROR'
                    END
                FROM {SCHEMA_NAME}.{TABLE_STAGING}
                WHERE id !~* '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$'
                   OR price !~ '^[0-9]+(\\.[0-9]{{1,2}})?$';
            """)

            # 2. Insert valid rows into strongly typed inventory table
            cur.execute(f"""
                INSERT INTO {SCHEMA_NAME}.{TABLE_TARGET} (
                    id, sku, name, price, stock, category, warehouse_id, created_at
                )
                SELECT
                    id::uuid,
                    sku,
                    name,
                    price::numeric(10, 2),
                    stock::integer,
                    category,
                    warehouse_id,
                    created_at::timestamptz
                FROM {SCHEMA_NAME}.{TABLE_STAGING}
                WHERE id ~* '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$'
                  AND price ~ '^[0-9]+(\\.[0-9]{{1,2}})?$';
            """)
        conn.commit()
        validation_elapsed = time.perf_counter() - validation_start

        # Read quarantined rows and export to CSV
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT id, sku, name, price, stock, category, warehouse_id, created_at, quarantine_reason
                FROM {SCHEMA_NAME}.{TABLE_QUARANTINE};
            """)
            quarantine_rows = cur.fetchall()

            cur.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.{TABLE_TARGET};")
            valid_count = cur.fetchone()[0]

            cur.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.{TABLE_QUARANTINE};")
            quarantine_count = cur.fetchone()[0]

        # Write quarantined rows CSV to both output directory and root
        quarantine_cols = ["id", "sku", "name", "price", "stock", "category", "warehouse_id", "created_at", "quarantine_reason"]
        for target_csv in [QUARANTINE_CSV_OUTPUT, QUARANTINE_CSV_ROOT]:
            with open(target_csv, "w", encoding="utf-8", newline="") as fcsv:
                writer = csv.writer(fcsv)
                writer.writerow(quarantine_cols)
                for qrow in quarantine_rows:
                    writer.writerow(qrow)
            print(f"Saved quarantined rows CSV to {target_csv}")

        final_rss_mb = process.memory_info().rss / (1024 * 1024)
        peak_rss_mb = max(initial_rss_mb, peak_rss_during_copy_mb, final_rss_mb)
        total_pipeline_seconds = stage_elapsed + validation_elapsed

        print(f"Quarantine probe completed in {total_pipeline_seconds:.3f}s:")
        print(f"  Staging rows ingested: {staging_count:,}")
        print(f"  Valid rows committed to {TABLE_TARGET}: {valid_count:,}")
        print(f"  Dirty rows quarantined: {quarantine_count:,}")
        print(f"  Peak RSS memory: {peak_rss_mb:.2f} MB")

        metrics = {
            "probe_name": "Dirty Row Quarantine Probe",
            "task_id": "t_7abdcdec",
            "artifact_id": "D12",
            "round": "R2",
            "dataset": {
                "file": csv_path,
                "file_size_bytes": total_bytes_streamed,
                "file_size_mb": round(total_bytes_streamed / (1024 * 1024), 2),
                "total_rows_streamed": staging_count,
            },
            "quarantine_results": {
                "staging_rows_ingested": staging_count,
                "valid_rows_committed": valid_count,
                "dirty_rows_isolated": quarantine_count,
                "expected_valid_rows": 499999,
                "expected_dirty_rows": 1,
                "batch_aborted": False,
                "quarantine_csv": QUARANTINE_CSV_OUTPUT,
                "sample_quarantined_record": {
                    "id": quarantine_rows[0][0] if quarantine_rows else None,
                    "price": quarantine_rows[0][3] if quarantine_rows else None,
                    "reason": quarantine_rows[0][8] if quarantine_rows else None,
                },
            },
            "performance": {
                "staging_copy_seconds": round(stage_elapsed, 4),
                "validation_and_insert_seconds": round(validation_elapsed, 4),
                "total_pipeline_seconds": round(total_pipeline_seconds, 4),
                "effective_throughput_rows_per_sec": round(staging_count / total_pipeline_seconds, 2),
            },
            "memory": {
                "initial_rss_mb": round(initial_rss_mb, 2),
                "peak_rss_mb": round(peak_rss_mb, 2),
                "final_rss_mb": round(final_rss_mb, 2),
                "target_max_rss_mb": 35.0,
                "memory_gate_passed": peak_rss_mb <= 35.0,
            },
            "acceptance_criteria_verified": (
                staging_count == 500000
                and valid_count == 499999
                and quarantine_count == 1
                and peak_rss_mb <= 35.0
            ),
        }

        with open(METRICS_PATH, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        print(f"Metrics saved to {METRICS_PATH}")
        return metrics

    finally:
        conn.close()


if __name__ == "__main__":
    run_quarantine_probe()
