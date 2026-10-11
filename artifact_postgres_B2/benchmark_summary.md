# Concurrency & Deadlock Benchmark Summary

| Metric | Before Remediation | After Remediation | Business Impact |
|---|---|---|---|
| **Total Transactions** | 2 competing transactions | **500** | High concurrency verified across 500 loops |
| **Min Execution Latency** | 1,218.22 ms | **0.88 ms** | Sub-millisecond baseline latency |
| **Max Execution Latency** | 1,237.92 ms (1,218.22 ms abort) | **134.25 ms** | Predictable bounded latency under contention |
| **Mean / Average Execution Latency** | 1,228.07 ms | **8.91 ms** | High transaction throughput |
| **p95 Execution Latency** | 1,237.92 ms | **54.28 ms** | 95% of transactions complete in under 55 ms |
| **Deadlocks Encountered** | 1 (deadlock detected) | **0** | Complete elimination of lock cycles |
| **Deadlock Rate** | 100% on competing transactions | **0.0% (Zero deadlocks)** | Checkout outages eliminated |
| **Unindexed Foreign Keys** | 2 unindexed relationships | **2 concurrent B-Tree indexes** | Cascading table locks prevented |
| **Transaction Failure Rate** | 50% (HTTP 500 on abort) | **0% (100% success)** | Zero lost revenue |
