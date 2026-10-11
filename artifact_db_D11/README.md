# Artifact D11: PostgreSQL Composite & Partial Index Optimization

Part of the Albidox Enterprise Backend Engineering Portfolio.
Service 13: PostgreSQL Composite Indexing & Partial Index Setup.

## Overview

This repository demonstrates high-performance indexing architecture in PostgreSQL 18.0. In high-volume online transaction processing (OLTP) environments, transactional tables frequently accumulate millions of rows where only a small minority (e.g. 5%) represent active, frequently queried records.

Indexing the entire table using a standard composite B-Tree index wastes significant disk space and incurs write amplification overhead on every insert, update, and vacuum cycle. By engineering a partial index targeting only active records, disk footprint is reduced by 97.17% while achieving sub-0.1ms query performance.

## Architecture & Schema

- Database: PostgreSQL 18.0 (Port 5433)
- Isolated Schema: `d11_indexing_sandbox`
- Table: `orders` (1,000,000 records)
  * `order_id`: BIGSERIAL PRIMARY KEY
  * `tenant_id`: UUID NOT NULL
  * `status`: VARCHAR(32) NOT NULL (Distribution: ~5% ACTIVE, ~70% COMPLETED, ~25% ARCHIVED)
  * `amount`: NUMERIC(10, 2) NOT NULL
  * `created_at`: TIMESTAMPTZ NOT NULL
  * `metadata`: JSONB NOT NULL DEFAULT '{}'::jsonb

## Indexes Evaluated

1. Baseline Composite Index:
   ```sql
   CREATE INDEX idx_orders_composite_status_created
   ON d11_indexing_sandbox.orders (status, created_at DESC);
   ```
   Indexes all 1,000,000 rows. Disk Footprint: 38.32 MB.

2. Optimized Partial Index:
   ```sql
   CREATE INDEX idx_orders_partial_active_created
   ON d11_indexing_sandbox.orders (created_at DESC)
   WHERE status = 'ACTIVE';
   ```
   Indexes only ~50,000 active rows. Disk Footprint: 1.09 MB (97.17% footprint reduction).

3. Optimized JSONB Expression Partial Index:
   ```sql
   CREATE INDEX idx_orders_partial_urgent_jsonb
   ON d11_indexing_sandbox.orders (created_at DESC)
   WHERE ((metadata->>'urgent')::boolean = true);
   ```
   Indexes only urgent document flags (~12,500 rows). Disk Footprint: 296.00 KB.

## Key Performance Results

- Sequential Scan Latency: 163.33 ms (77,144 shared buffer blocks)
- Partial Index Scan Latency: 0.099 ms (104 shared buffer blocks)
- Server Speedup: 1,649.8x execution acceleration
- Memory Reduction: 99.87% reduction in shared buffer reads
- Storage Footprint Reduction: 97.17% savings (1.09 MB vs 38.32 MB)
- Write Amplification Elimination: 100.0% of inactive index writes eliminated, 95.0% write overhead eliminated across 95/5 workload
- JSONB Expression Query Latency: 0.14 ms (sub-millisecond) with 296 KB index footprint

## Quick Start & Reproduction

```bash
# Setup Python 3.11 virtual environment
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

# Seed 1,000,000 orders
.venv/Scripts/python seed_orders.py

# Create database indexes
"C:/Program Files/PostgreSQL/18/bin/psql.exe" -p 5433 -U postgres -d postgres -f create_indexes.sql

# Execute 1,000 query benchmark suite
.venv/Scripts/python benchmark_indexes.py

# Execute Round 2 Real-World Stress Probe and Write Amplification Audit
.venv/Scripts/python stress_probe_d11.py
```
