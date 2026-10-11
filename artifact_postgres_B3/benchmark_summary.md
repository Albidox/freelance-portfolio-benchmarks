# PostgreSQL JSONB Indexing Benchmark Summary

## Empirical Performance Comparison

| Metric | Sequential Scan (Baseline) | GIN (jsonb_path_ops) | B-Tree Expression Index | Recommended Choice |
|---|---|---|---|---|
| **Query Latency / Execution Time** | 250.18 ms | **0.56 ms** | **0.36 ms** | **B-Tree Expression (698.8x faster)** |
| **Planning Time** | 2.01 ms | 3.20 ms | 3.55 ms | B-Tree Expression |
| **Access Method** | Parallel Seq Scan (2 workers) | Bitmap Index Scan | **Index Scan (Direct)** | B-Tree Expression |
| **Shared Buffers Hit (RAM)** | 11,158 blocks | 34 blocks | 53 blocks | GIN / B-Tree |
| **Shared Buffers Read (Disk)** | 28,305 blocks | 0 blocks | 0 blocks | Zero Disk Reads |
| **Total Shared Buffers** | 39,463 blocks | **34 blocks** | **53 blocks** | 99.86% I/O Reduction |
| **Index Size on Disk** | 0 MB (No index) | 74 MB | **37 MB** | **B-Tree is 50.0% smaller** |
| **Table Data Size** | 308 MB | 308 MB | 308 MB | Base table heap storage |
| **Total Table Size (incl. indexes)**| 308 MB | 457 MB | 457 MB | Combined heap + indexes |
| **Query Pattern Fit** | None (Fails SLA) | Arbitrary `@>` key search | Fixed key + sort order | Workload-dependent |

## Strategy Assessment

1. **Strategy A: Functional B-Tree Expression Index (`idx_audit_events_action_created`)**
   - Index Definition: `ON audit_events ((metadata->>'action_type'), created_at DESC)`
   - Latency: 0.358 ms (698.8x speedup over sequential scan).
   - Storage Footprint: 37 MB (12.0% of base table size).
   - Strengths: Directly satisfies compound filter and ordering clauses without post-filtering or sorting steps. Lowest memory and cache overhead.
   - Tradeoff: Only accelerates queries filtering on the exact extracted expression `metadata->>'action_type'`.

2. **Strategy B: GIN Containment Index (`idx_audit_events_metadata_path_ops`)**
   - Index Definition: `ON audit_events USING gin (metadata jsonb_path_ops)`
   - Latency: 0.560 ms (446.8x speedup over sequential scan).
   - Storage Footprint: 74 MB (24.0% of base table size, exactly 2.0x larger than B-Tree expression index).
   - Strengths: Accelerates arbitrary JSON document containment queries (`@>`) across all top-level and nested key combinations without schema-specific indexing.
   - Tradeoff: Larger index footprint, higher maintenance cost during high-throughput writes, and cannot supply index-ordered scans for sorting.
