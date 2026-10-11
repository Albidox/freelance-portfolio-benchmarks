# Massive 500k Row Postgres Streaming COPY Ingestion Pipeline (Artifact D12)

High-throughput data ingestion pipeline demonstrating client-side stream buffering and PostgreSQL 18 `COPY FROM STDIN` execution. Loads 500,000 typed rows in under 4.0 seconds while maintaining a minimal host process memory footprint under 21 MB RAM.

## Architecture & Engineering Highlights

- **Direct Socket Streaming:** Uses `psycopg2.cursor.copy_expert()` with a chunked buffer adapter, streaming data directly from disk to the PostgreSQL socket without buffering whole datasets in RAM.
- **High Throughput:** Reaches over 126,000 rows/second (16.2 MB/s wire throughput) on native PostgreSQL 18.
- **Minimal RAM Footprint:** Host Python process consumes only ~20.3 MB peak RAM, avoiding the high memory overhead of ORM/batch loads.
- **Database Engine:** PostgreSQL 18 on port 5433 with schema `d12_copy_sandbox`.
- **Dirty Row Quarantine:** Two-stage atomic validation routes corrupted rows (invalid UUID, non-numeric price) into `quarantined_rows.csv` without aborting the ingestion batch of 499,999 valid rows.
- **Unlogged Table Acceleration:** Streaming into an `UNLOGGED` staging table achieves over 131,000 rows/second and eliminates 54.7 MB of WAL disk writes during bulk ingest (up to 100% WAL reduction during copy), followed by atomic promotion via `ALTER TABLE SET LOGGED`.
- **Fault-Tolerant Atomic Rollback:** Forcefully severing the database socket mid-flight at row 300,000 confirms PostgreSQL cleanly unwinds uncommitted transactions, leaving 0 partial or orphaned records.

## Table Schema

Target table: `d12_copy_sandbox.inventory`

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Primary record UUID |
| `sku` | VARCHAR(64) | Stock keeping unit identifier |
| `name` | VARCHAR(255) | Product name |
| `price` | NUMERIC(10, 2) | Unit sale price |
| `stock` | INTEGER | Current available stock quantity |
| `category` | VARCHAR(64) | Product taxonomy category |
| `warehouse_id` | VARCHAR(32) | Regional distribution center ID |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

## Benchmark Results

### Round 1: Ingestion Method Comparison (500,000 Rows)

| Ingestion Method | Throughput (rows/sec) | Extrapolated 500k Time | Relative Speedup |
| :--- | :--- | :--- | :--- |
| Single-Row INSERT | 7,181.8 rows/sec | 69.6 seconds | Baseline (1.0x) |
| Batched INSERT (`execute_values`, 1000/page) | 33,867.5 rows/sec | 14.8 seconds | 4.7x faster |
| **Streaming COPY FROM STDIN** | **126,522.5 rows/sec** | **3.95 seconds** | **17.6x faster** |

### Round 2: Real-World Stress Probes

| Probe Scenario | Target | Key Result | Verification Status |
| :--- | :--- | :--- | :--- |
| **Dirty Row Quarantine** | Row 250,000 corrupted | 499,999 valid rows committed; 1 dirty row isolated to `quarantined_rows.csv` | PASS (Zero batch abort) |
| **Unlogged Acceleration** | 500,000 rows | 131,350 rows/sec; 54.7 MB WAL saved during ingestion (100% reduction) | PASS (Speedup demonstrated) |
| **Mid-Flight Disconnect** | Terminated at row 300,000 | 0 partial rows surviving; 0 stray locks; atomic rollback verified | PASS (Clean ACID rollback) |

## File Manifest

- `generate_massive_dataset.py`: Generates realistic 500,000 row CSV dataset (`inventory_500k.csv`, 64.1 MB).
- `generate_corrupted_dataset.py`: Injects malformed records at row 250,000 (`inventory_500k_dirty.csv`).
- `ingest_pipeline.py`: Production streaming pipeline executing `COPY FROM STDIN` with socket chunking.
- `benchmark_ingestion.py`: Comparative benchmark measuring throughput and memory across ingestion strategies.
- `init_db.py`: Database schema and table DDL initialization.
- `quarantine_probe.py`: Staging-table atomic validation isolating malformed rows without batch abort.
- `unlogged_acceleration_probe.py`: PostgreSQL WAL disk write volume and throughput acceleration benchmark.
- `midflight_disconnect_probe.py`: Database socket termination probe verifying atomic transaction rollback.
- `run_stress_probe.py`: End-to-end stress probe orchestrator generating comprehensive Markdown report.
- `verify_d12_r1.py`: Automated verification harness for Round 1 deliverables.
- `verify_d12_r2.py`: Automated verification harness for Round 2 deliverables.
- `quarantined_rows.csv`: Exported malformed record with error classification.
- `output/ingestion_metrics.json`: Hardware, timing, and memory telemetry.
- `output/benchmark_comparison.json`: Comparative execution metrics.
- `output/quarantine_metrics.json`: Dirty row quarantine probe metrics.
- `output/unlogged_bench_metrics.json`: Empirical WAL savings and throughput benchmarks.
- `output/disconnect_probe_metrics.json`: Mid-flight socket disconnection and atomic rollback proofs.
- `output/quarantined_rows.csv`: Output directory copy of quarantined records.
- `output/postgres_copy_ingestion_report.md`: Complete engineering and stress probe report.
- `output/SHA256SUMS.txt`: Cryptographic SHA-256 integrity manifest.

## Reproduction Instructions

```bash
# 1. Activate isolated Python 3.11 virtual environment
.venv/Scripts/python -m pip install -r requirements.txt

# 2. Initialize database schema
.venv/Scripts/python init_db.py

# 3. Generate 500,000 row dataset
.venv/Scripts/python generate_massive_dataset.py

# 4. Execute streaming COPY ingestion pipeline
.venv/Scripts/python ingest_pipeline.py

# 5. Run comparative benchmark suite
.venv/Scripts/python benchmark_ingestion.py

# 6. Run Round 2 real-world stress probe suite
.venv/Scripts/python run_stress_probe.py

# 7. Run full verification test harness
.venv/Scripts/python verify_d12_r2.py
```
