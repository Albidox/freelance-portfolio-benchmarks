# Artifact B2-R1: PostgreSQL Deadlock & Lock Contention Remediation

## Objective
This repository contains a full empirical reproduction and remediation of PostgreSQL checkout deadlocks caused by unindexed foreign keys and non-deterministic row locking.

## Overview
- **Pathology**: Unindexed foreign keys trigger table-level locks, causing a cyclic dependency (`deadlock detected`) under concurrent updates.
- **Remediation**: `CONCURRENTLY` applied B-Tree indexes on foreign keys plus deterministic `ORDER BY id FOR UPDATE` lock acquisition.
- **Outcome**: 100% elimination of deadlocks with 0% failure rate across high-concurrency transaction loads.

## Usage Guide
1. **Seed Data:**
   Run `seed_data.sql` to populate 150,000 unindexed records.
2. **Reproduce Pathology:**
   Execute `python reproduce_deadlock.py` to trigger a deadlock (captures graph to `output/deadlock_before.txt`).
3. **Remediate:**
   Deploy `V3__fix_fk_indexes_and_locking.sql` to add safe concurrent indexing.
4. **Verify Fix:**
   Execute `python remediate_deadlock.py` to verify 100% transaction success (`output/deadlock_after.txt`).

## Benchmark Metrics
| Metric | Before Remediation | After Remediation |
|---|---|---|
| **Total Transactions** | 2 | **500** |
| **Min Execution Latency** | 1,218.22 ms | **0.88 ms** |
| **Max Execution Latency** | 1,237.92 ms | **134.25 ms** |
| **Mean / Average Execution Latency** | 1,228.07 ms | **8.91 ms** |
| **p95 Execution Latency** | 1,237.92 ms | **54.28 ms** |
| **Deadlocks Encountered** | 1 | **0** |
| **Deadlock Rate** | 100% | **0.0%** |
| **Failure Rate** | 50% | **0%** |

## Author Attribution
- **Author**: Sk Ashfaq Bux (`github.com/Albidox`)
- **Focus**: PostgreSQL Concurrency Optimization, Lock Remediation, Database Performance
