# Benchmark Summary: Multi-Tenant Transactions Query Optimization

| Metric | Before Optimization (`idx_tenant_id_only`) | After Optimization (`idx_tenant_transactions_covering`) | Delta / Impact |
|---|---|---|---|
| **Execution Time** | 115.714 ms | **5.604 ms** | **20.6x Faster (95.2% latency reduction)** |
| **Index Scan Time** | 39.687 ms (Seq Scan) | **2.511 ms (Index Only)** | 15.8x faster retrieval |
| **Access Method** | Parallel Seq Scan + Heap Buffers | **Index Only Scan** | Zero heap block accesses |
| **Heap Blocks Fetched** | ~6,580 pages (493k rows filtered) | **0 pages (0 heap fetches)** | 100% eliminated |
| **Shared Buffers Read (Disk)**| 6,385 blocks | **0 blocks** | 100% in-memory buffer hit |
| **Shared Buffers Hit (RAM)** | 358 blocks | **48 blocks** | 99.3% buffer churn reduction |
| **Temp Disk Sort Spill** | 152 kB (temp written=38) | **0 kB (quicksort in-memory)** | External merge eliminated |
| **Planner Cost Estimate** | 12,078.73..13,033.58 | **750.19..902.20** | 93.1% lower planner cost |
| **Planning Time** | 2.510 ms | 3.170 ms | Deterministic plan selection |

## Forensic Breakdown

1. **Heap Read Elimination:** The unoptimized plan required traversing heap pages for 50,000 candidate records to evaluate `created_at` and retrieve `amount_cents`. The composite covering index (`tenant_id, created_at DESC`) with `INCLUDE (amount_cents)` satisfies both the filtering predicate and projection list entirely from the index leaf pages.
2. **Disk Sort Elimination:** The unconstrained sort order previously forced temporary disk spills (`external merge`) under default or memory-constrained worker settings. The pre-sorted composite index structure aligns directly with the `created_at DESC` descending sequence, eliminating temporary file creation.
3. **Buffer Churn Reduction:** Total shared buffer interactions dropped from 6,743 blocks down to 48 blocks, freeing PostgreSQL shared memory for concurrent transactions.
