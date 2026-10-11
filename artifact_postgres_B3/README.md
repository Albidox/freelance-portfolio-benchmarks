# Artifact B3: PostgreSQL JSONB Document Profiling & Indexing

**Author:** Sk Ashfaq Bux ([github.com/Albidox](https://github.com/Albidox))  
**Target:** PostgreSQL 13+ / 16+ / 18  
**Specialization:** Database Performance Audits, Semi-Structured Data Profiling, JSONB Indexing Architecture  

---

## Overview

This repository contains an end-to-end performance audit resolving full-table sequential scans on a 1,000,000-row semi-structured audit event ledger (`audit_events` with `metadata JSONB`).

Standard B-Tree indexes cannot index properties within semi-structured JSON documents directly. Queries filtering on dynamic document fields force PostgreSQL into sequential heap scans, reading tens of thousands of disk blocks and exceeding acceptable latency thresholds.

This artifact implements and benchmarks two competing production indexing strategies:
1. **Strategy A (Functional B-Tree Expression Index):** Indexes the specific extracted JSON key combined with timestamp ordering (`(metadata->>'action_type', created_at DESC)`).
2. **Strategy B (GIN jsonb_path_ops Index):** Indexes hashed document paths to accelerate arbitrary multi-key containment queries (`@>`).

---

## Verified Benchmark Results

All figures below are taken directly from genuine EXPLAIN (ANALYZE, BUFFERS) execution plans in `output/`:

| Metric | Sequential Scan (Baseline) | GIN (jsonb_path_ops) | B-Tree Expression Index | Performance Delta |
|---|---|---|---|---|
| **Query Latency / Execution Time** | 250.18 ms | **0.56 ms** | **0.36 ms** | **698.8x faster (B-Tree)** |
| **Planning Time** | 2.01 ms | 3.20 ms | 3.55 ms | Low planning overhead |
| **Access Method** | Parallel Seq Scan (2 workers) | Bitmap Index Scan | **Index Scan (Direct)** | Direct index traversal |
| **Shared Buffers Hit (RAM)** | 11,158 blocks | 34 blocks | 53 blocks | In-memory evaluation |
| **Shared Buffers Read (Disk)** | 28,305 blocks | 0 blocks | 0 blocks | 100% disk reads eliminated |
| **Total Shared Buffers** | 39,463 blocks | **34 blocks** | **53 blocks** | **99.86% I/O reduction** |
| **Index Size on Disk** | 0 MB (No index) | 74 MB | **37 MB** | B-Tree is 50.0% smaller |
| **Base Table Size** | 308 MB | 308 MB | 308 MB | 1,000,000 heap rows |
| **Total Relation Size** | 308 MB | 457 MB | 457 MB | Heap + all secondary indexes |

---

## Disk Storage Footprint Comparison

Raw measurements from `output/index_storage_comparison.txt` via `pg_relation_size`:

| Relation / Object Name | Data Size | Total Size | Description |
|---|---|---|---|
| `audit_events` | 308 MB | 457 MB | Base heap table containing 1,000,000 rows |
| `idx_audit_events_action_created` | 37 MB | 37 MB | Composite B-Tree functional expression index |
| `idx_audit_events_metadata_path_ops` | 74 MB | 74 MB | Generalized Inverted Index using `jsonb_path_ops` |

**Key Takeaways:**
- The B-Tree expression index occupies **37 MB**, representing **12.0%** of the base table size.
- The GIN `jsonb_path_ops` index occupies **74 MB**, which is **2.0x larger** than the B-Tree index, but provides comprehensive search flexibility across all JSON keys.

---

## Repository Structure

```text
artifact_postgres_B3/
├── POSTGRES_JSONB_INDEXING_REPORT.md      # Flagship client deliverable and technical report
├── jsonb_architecture_decision_matrix.md  # Architectural decision matrix and production guide
├── README.md                              # Summary, benchmark matrix, and reproduction guide
├── benchmark_summary.md                   # Metric delta comparison table
├── seed_data.sql                          # 1,000,000 JSONB row seed generator
├── broken_query.sql                       # Unindexed slow JSONB query
├── V4__jsonb_expression_index.sql         # Idempotent zero-downtime production migration
├── V4__optimize_jsonb_queries.sql         # Idempotent production migration alias
├── rollback_V4.sql                        # Zero-downtime rollback DDL
├── rollback.sql                           # Idempotent rollback DDL alias
└── output/
    ├── query_before.txt                   # Raw Seq Scan EXPLAIN plan (250.18 ms)
    ├── query_after_btree.txt              # Raw B-Tree Expression EXPLAIN plan (0.36 ms)
    ├── query_after_gin.txt                # Raw GIN Containment EXPLAIN plan (0.56 ms)
    └── index_storage_comparison.txt       # Raw disk size measurement output
```

---

## Reproduction Runbook

Follow these commands to reproduce the benchmark in a local PostgreSQL 16+ or 18 environment:

### 1. Seed 1,000,000 JSONB Records

```bash
psql -p 5433 -U postgres -d postgres -f seed_data.sql
```

This creates `audit_events` and inserts 1,000,000 rows with varied JSONB payloads using `generate_series()`, `jsonb_build_object()`, and `ANALYZE`.

### 2. Capture Baseline Sequential Scan Plan

```bash
psql -p 5433 -U postgres -d postgres -f broken_query.sql > output/query_before.txt
```

Verify that `output/query_before.txt` demonstrates a full-table sequential scan scanning 1,000,000 rows and reading tens of thousands of buffer blocks.

### 3. Apply Zero-Downtime Migration

```bash
psql -p 5433 -U postgres -d postgres -f V4__jsonb_expression_index.sql
```

Applies both indexing strategies concurrently without table write locks:
```sql
SET lock_timeout = '5s';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_events_action_created
ON audit_events ((metadata->>'action_type'), created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_events_metadata_path_ops
ON audit_events USING gin (metadata jsonb_path_ops);

ANALYZE audit_events;
```

### 4. Benchmark B-Tree Expression Index Strategy

```bash
psql -p 5433 -U postgres -d postgres -c "EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING) SELECT id, user_id, created_at, metadata->>'ip_address' AS client_ip, metadata->>'session_id' AS session_id FROM audit_events WHERE metadata->>'action_type' = 'USER_LOGIN' AND created_at >= NOW() - INTERVAL '30 days' ORDER BY created_at DESC LIMIT 50;" > output/query_after_btree.txt
```

Verify sub-millisecond execution time (`0.36 ms`) and direct `Index Scan`.

### 5. Benchmark GIN Containment Index Strategy

```bash
psql -p 5433 -U postgres -d postgres -c "EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING) SELECT id, user_id, created_at, metadata->>'ip_address' AS client_ip, metadata->>'session_id' AS session_id FROM audit_events WHERE metadata @> '{\"action_type\": \"USER_LOGIN\", \"ip_address\": \"192.168.1.10\"}' LIMIT 50;" > output/query_after_gin.txt
```

Verify sub-millisecond execution time (`0.56 ms`) and `Bitmap Index Scan`.

### 6. Verify Relation Sizes

```bash
psql -p 5433 -U postgres -d postgres -c "SELECT relname AS object_name, pg_size_pretty(pg_relation_size(c.oid)) AS data_size, pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE relname IN ('audit_events', 'idx_audit_events_action_created', 'idx_audit_events_metadata_path_ops') ORDER BY relname;" > output/index_storage_comparison.txt
```

---

## Architectural Decision Matrix

| Dimension | B-Tree Expression Index | GIN (`jsonb_path_ops`) Index | Default GIN (`jsonb_ops`) |
|---|---|---|---|
| **Best Query Pattern** | Known key with equality/range filter and sort | Arbitrary JSON containment (`@>`) | Key existence (`?`, `?|`, `?&`) and containment |
| **Index Size** | Smallest (37 MB) | Compact (74 MB, ~50% of default GIN) | Largest (~140 MB+) |
| **Index Maintenance / Write Overhead** | Lowest (Standard B-Tree leaf insert) | Moderate (Hashed path inverted lists) | Highest (Inverted list per key and value) |
| **Sort Capability** | Supports index ordering (`ORDER BY created_at`) | No index ordering support | No index ordering support |
| **Recommendation** | Core analytical and dashboard queries | Ad-hoc multi-attribute document search | Highly dynamic document property presence checks |

---

## Author Attribution

- **Author:** Sk Ashfaq Bux ([github.com/Albidox](https://github.com/Albidox))
- **Role:** Senior Database Engineer and Backend Performance Specialist
- **Core Skills:** PostgreSQL Query Optimization, JSONB Document Indexing, Concurrency Remediation, Zero-Downtime Migrations
