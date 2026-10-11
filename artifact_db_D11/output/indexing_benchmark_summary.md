# Artifact D11: PostgreSQL Composite & Partial Index Optimization Benchmark Summary

## Executive Summary
This benchmark evaluates query latency, shared buffer memory consumption, and physical disk storage footprint for 1,000,000 synthetic orders in PostgreSQL 18.0. The workload represents typical multi-tenant SaaS workloads where only 5% of records are in an ACTIVE operational state, while 95% reside in terminal states (COMPLETED or ARCHIVED).

## Core Benchmark Metrics

| Metric | Sequential Scan Baseline | Full Composite Index | Optimized Partial Index | Improvement vs Baseline |
| :--- | :--- | :--- | :--- | :--- |
| Scan Node Type | Parallel Seq Scan | Index Scan | Index Scan | Direct B-Tree Seek |
| Index Expression | None (Heap Scan) | `(status, created_at DESC)` | `(created_at DESC) WHERE status = 'ACTIVE'` | 95% Predicate Elimination |
| Execution Latency | 163.33 ms | 0.83 ms | 0.099 ms (sub-0.1ms) | 1,649.8x Speedup |
| Client Latency (p50) | 145.44 ms | 0.58 ms | 0.54 ms | 267.3x Speedup |
| Client Latency (p95) | 170.20 ms | 1.22 ms | 1.15 ms | 148.0x Speedup |
| Shared Buffer Blocks | 77,144 blocks | 106 blocks | 104 blocks | 99.87% Memory Reduction |
| Index Disk Footprint | 0 bytes (Heap: 150.23 MB) | 38.32 MB (40,181,760 B) | 1.09 MB (1,138,688 B) | 97.17% Storage Reduction |

## Acceptance Criteria Verification

1. Query Latency Reduction:
   - Baseline Sequential Scan: 163.33 ms (> 100 ms).
   - Partial Index Scan: 0.099 ms (< 0.1 ms sub-millisecond).
   - Verdict: PASSED.

2. Physical Disk Storage Reduction:
   - Composite Index: 38.32 MB.
   - Partial Index: 1.09 MB.
   - Reduction: 37.23 MB (97.17% reduction vs required >= 75%).
   - Verdict: PASSED.

3. Complete SHA-256 Manifest:
   - Output files hashed and registered in `output/SHA256SUMS.txt`.
   - Verdict: PASSED.

4. Stylistic Invariant:
   - Zero em dashes across all code, manifests, and documentation.
   - Verdict: PASSED.
