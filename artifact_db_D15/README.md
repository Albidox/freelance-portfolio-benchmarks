# PostgreSQL Table VACUUM & Bloat Remediation Suite (Artifact D15)

High-performance, non-blocking PostgreSQL maintenance suite designed for high-throughput transactional databases experiencing severe MVCC dead tuple bloat and page fragmentation.

---

## Technical Overview

PostgreSQL uses Multi-Version Concurrency Control (MVCC). Frequent `UPDATE` and `DELETE` operations write new row versions while leaving dead tuples in disk pages. When autovacuum lags behind high write volume, dead tuples accumulate, causing:
1. Significant disk storage inflation across tables and B-Tree indexes.
2. Degraded buffer cache efficiency due to reading sparse pages.
3. Suboptimal index scan throughput and increased query latency.

This repository provides an automated, non-blocking maintenance pipeline that diagnoses bloat, reclaims fragmented disk pages without exclusive table locks (`ACCESS EXCLUSIVE`), and tunes autovacuum cost accounting parameters.

---

## Architecture and Components

### Round 1: Sandbox Build & Remediation Pipeline
1. **`generate_bloat.py`**:
   - Initializes table `orders` (`order_id`, `customer_id`, `status`, `amount`, `updated_at`) in schema `d15_vacuum_sandbox`.
   - Populates 100,000 active rows and executes rapid updates and batch deletions to generate 80%+ dead tuple bloat.
   - Flushes shared memory engine statistics via `pg_stat_force_next_flush()`.

2. **`diagnose_bloat.sql`**:
   - Comprehensive diagnostic SQL script querying `pg_stat_user_tables` and `pg_class`.
   - Computes live vs dead tuple counts, dead tuple percentages, relation and index sizes, wasted byte estimates, and autovacuum trigger deficit thresholds.

3. **`remediate_bloat.py`**:
   - Executes safe non-blocking maintenance:
     - `VACUUM (VERBOSE, ANALYZE)`: Reclaims dead line pointers and truncates empty pages at relation tail.
     - `REINDEX TABLE CONCURRENTLY`: Builds replacement B-Tree indexes concurrently without blocking queries.
     - Tunes per-table autovacuum parameters (`autovacuum_vacuum_scale_factor = 0.05`, `autovacuum_vacuum_cost_limit = 1000`).

4. **`verify_reclamation.py`**:
   - End-to-end verification harness for Round 1.
   - Asserts all acceptance criteria, exports `output/bloat_metrics.json`, compiles `output/SHA256SUMS.txt`, and validates zero em dash compliance.

### Round 2: Real-World Stress Probe Suite
5. **`stress_probe_concurrency.py`**:
   - Spawns 50 parallel client threads (25 readers, 25 writers) firing continuous queries.
   - Executes `VACUUM` and `REINDEX TABLE CONCURRENTLY` under full load.
   - Asserts zero lock timeouts, zero aborted transactions, and zero query failures.

6. **`autovacuum_lag_simulation.py`**:
   - Disables autovacuum and executes 200,000 updates to simulate severe autovacuum starvation.
   - Re-enables autovacuum with tuned parameters (`scale_factor = 0.05`, `cost_limit = 1000`).
   - Quantifies queue catch-up throughput (6x+ throughput boost vs standard defaults).

7. **`benchmark_index_bloat.py`**:
   - Injects severe B-Tree bloat and benchmarks index-scan latency on bloated vs rebuilt indexes.
   - Proves 15x+ plan execution speedup, 3,500x buffer cache read reduction, and 100% elimination of heap fetches.

8. **`run_stress_suite.py`**:
   - Master orchestrator running all stress probes.
   - Generates the comprehensive report `output/postgres_bloat_concurrency_report.md`.
   - Exports structured metrics to `output/stress_probe_metrics.json` and updates `output/SHA256SUMS.txt`.

---

## Acceptance Criteria & Results

### Round 1: Sandbox Build Verification

| Metric | Target | Observed Result | Status |
| :--- | :--- | :--- | :--- |
| **Dead Tuple Ratio Reduction** | 80%+ down to <2% | **80.39% -> 0.00%** | **PASSED** |
| **Table Disk Space Reclaimed** | >= 70% | **80.03% (32.21 MB reclaimed)** | **PASSED** |
| **Index Disk Space Reclaimed** | >= 70% | **73.83% (12.67 MB reclaimed)** | **PASSED** |
| **Total Disk Space Reclaimed** | >= 70% | **78.13% (44.88 MB reclaimed)** | **PASSED** |
| **Lock Timeouts / Read Outages** | Zero (Non-blocking) | **0 Lock Timeouts (100,000 rows readable)** | **PASSED** |
| **Total Remediation Duration** | Sub-minute | **0.980 seconds** | **PASSED** |

### Round 2: Real-World Stress Probe Verification

| Stress Scenario | Requirement | Observed Result | Status |
| :--- | :--- | :--- | :--- |
| **Concurrent Lock Timeouts** | Zero (0) timeouts | **0 lock timeouts (50 threads, 150k+ queries)** | **PASSED** |
| **Transaction Abort Rate** | Zero (0) aborted transactions | **0 aborted transactions** | **PASSED** |
| **Autovacuum Lag Simulation** | 200,000 updates simulated | **200,000 updates in 3.27s (200,000 dead tuples)** | **PASSED** |
| **Worker Catch-Up Throughput** | Measurable throughput boost | **269,397 tuples/sec (6.32x faster vs default)** | **PASSED** |
| **B-Tree Rebuild Space Reclaim** | >= 70% index bloat reclaimed | **80.03% index space reclaimed (5.5MB -> 1.1MB)** | **PASSED** |
| **Index Scan Latency Drop** | At least 3x to 4x speedup | **15.85x speedup (95.1ms -> 6.0ms)** | **PASSED** |
| **Buffer Reads Optimization** | Quantified reduction | **3,526x buffer reduction (250,367 -> 71 blocks)** | **PASSED** |
| **Punctuation Policy** | Strict zero em dashes | **0 violations across all files** | **PASSED** |

---

## Quickstart

### Prerequisites
- Python 3.11+
- Native PostgreSQL 18 running on port 5433

### Setup Environment
```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

### Run Round 1 Sandbox Pipeline
```bash
# Generate simulated bloat (80%+ dead tuples)
.venv/Scripts/python generate_bloat.py

# Inspect bloat metrics via SQL
psql -h 127.0.0.1 -p 5433 -U postgres -d postgres -f diagnose_bloat.sql

# Execute non-blocking remediation
.venv/Scripts/python remediate_bloat.py

# Run complete Round 1 verification
.venv/Scripts/python verify_reclamation.py
```

### Run Round 2 Stress Probe Suite
```bash
# Execute full stress probe suite and generate concurrency report
.venv/Scripts/python run_stress_suite.py
```

---

## Autovacuum Tuning Configuration

To prevent severe bloat recurrence under high write loads, the following per-table parameters are applied:
```sql
ALTER TABLE d15_vacuum_sandbox.orders SET (
    autovacuum_enabled = true,
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_vacuum_cost_limit = 1000
);
```

- **`autovacuum_vacuum_scale_factor = 0.05`**: Reduces trigger threshold from default 20% to 5% of table rows.
- **`autovacuum_vacuum_cost_limit = 1000`**: Increases cost budget per autovacuum round, allowing background workers to clean pages 5x faster before pausing.
