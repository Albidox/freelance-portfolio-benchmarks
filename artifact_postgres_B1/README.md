# Artifact B1: PostgreSQL Multi-Tenant Slow Query Optimization

**Author:** Sk Ashfaq Bux ([github.com/Albidox](https://github.com/Albidox))  
**Target:** PostgreSQL 13+ / 16+ / 18  
**Specialization:** Database Performance Audits, Query Profiling, Indexing Architecture

---

## Overview

This repository contains a reproducible, end-to-end performance audit that resolves a high-latency multi-tenant analytical dashboard query on a 500,000-row transactional table (`tenant_transactions`).

By replacing an inefficient single-column index with an idempotent zero-downtime composite covering index (`CREATE INDEX CONCURRENTLY ... INCLUDE`), the database access path shifts from an exhaustive heap scan to an in-memory **Index Only Scan**.

### Verified Benchmark Results

| Metric | Before Optimization (`idx_tenant_id_only`) | After Optimization (`idx_tenant_transactions_covering`) | Performance Delta |
|---|---|---|---|
| **Query Latency** | 115.714 ms | **5.604 ms** | **20.6x Faster (95.2% latency reduction)** |
| **Index Scan Time** | 39.687 ms | **2.511 ms** | **15.8x faster scan** |
| **Access Method** | Parallel Seq Scan + Heap Buffers | **Index Only Scan** | Direct index leaf evaluation |
| **Heap Blocks Fetched** | ~6,580 pages | **0 pages** | **100% heap reads eliminated** |
| **Shared Buffers Read (Disk)**| 6,385 blocks | **0 blocks** | 100% in-memory cache hit |
| **Shared Buffers Hit (RAM)** | 358 blocks | **48 blocks** | 99.3% buffer churn reduction |
| **Temp Disk Sort Spill** | 152 kB | **0 kB** | External merge sort eliminated |
| **Planner Estimated Cost** | 12,078.73..13,033.58 | **750.19..902.20** | 93.1% reduction in query cost |

---

## Repository Structure

```text
artifact_postgres_B1/
├── POSTGRES_OPTIMIZATION_REPORT.md        # Flagship client-facing audit report
├── README.md                              # Summary and reproduction runbook
├── benchmark_summary.md                   # Metric delta comparison table
├── production_database_tuning_guide.md    # Production parameters and logging audit guide
├── postgres_runtime_tuning.conf           # Production runtime parameter configuration
├── client_logging_setup.sql               # Non-invasive dynamic logging script
├── seed_data.sql                          # 500,000-row multi-tenant seed generator
├── broken_query.sql                       # Analytical dashboard aggregate query
├── query_before.txt                       # Raw baseline EXPLAIN (ANALYZE, BUFFERS)
├── query_after.txt                        # Raw optimized EXPLAIN (ANALYZE, BUFFERS)
├── V2__optimize_tenant_transactions.sql   # Zero-downtime concurrent covering migration
├── rollback_V2.sql                        # Zero-downtime rollback migration
├── rollback.sql                           # Idempotent rollback migration
├── pgbadger_report.html                   # Interactive pgBadger log analysis report (1.24 MB)
└── output/                                # Mirrored audit deliverables
    ├── query_before.txt
    ├── query_after.txt
    ├── pgbadger_report.html
    ├── production_database_tuning_guide.md
    ├── postgres_runtime_tuning.conf
    └── client_logging_setup.sql
```

---

## Reproduction Runbook

Follow these steps to reproduce the exact benchmark results in a local PostgreSQL environment:

### 1. Initialize Sandbox Database

```bash
# Connect to PostgreSQL cluster
psql -h 127.0.0.1 -p 5433 -U postgres
```

### 2. Seed 500,000 Multi-Tenant Records

```bash
psql -h 127.0.0.1 -p 5433 -U postgres -f seed_data.sql
```

This seeds 500,000 rows across 10 distinct tenant UUIDs, establishes the naive single-column index (`idx_tenant_id_only`), and updates catalog statistics (`ANALYZE`).

### 3. Capture Baseline Unoptimized Plan

```bash
psql -h 127.0.0.1 -p 5433 -U postgres -f broken_query.sql > query_before.txt
```

Verify that `query_before.txt` demonstrates heap scans, filter rejections, and disk sort spills.

### 4. Execute Zero-Downtime Migration

```bash
psql -h 127.0.0.1 -p 5433 -U postgres -f V2__optimize_tenant_transactions.sql
```

Applies the composite covering index concurrently without table locks:
```sql
SET lock_timeout = '5s';
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenant_transactions_covering
ON tenant_transactions (tenant_id, created_at DESC)
INCLUDE (amount_cents);
ANALYZE tenant_transactions;
```

### 5. Capture Optimized Plan

```bash
psql -h 127.0.0.1 -p 5433 -U postgres -f broken_query.sql > query_after.txt
```

Verify that `query_after.txt` demonstrates a sub-10ms Index Only Scan with 0 heap fetches.

### 6. Generate pgBadger Profiling Report

```bash
pgbadger --prefix '%m [%p] %q%u@%d ' -f stderr -o pgbadger_report.html /path/to/postgres.log
```

Open `pgbadger_report.html` in any web browser to view interactive latency histograms, query distributions, and checkpoint statistics.
