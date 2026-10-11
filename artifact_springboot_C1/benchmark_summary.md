# Hibernate N+1 Query Elimination Benchmark Summary

| Metric | Unoptimized Baseline (Before) | EntityGraph Optimization (After) | Delta / Impact |
|---|---|---|---|
| **SQL Queries Fired** | 51 queries | **1 query** | **98.0% Query Reduction** |
| **Database Round-Trips** | 51 round-trips | **1 round-trip** | 50 network traversals saved |
| **Response Duration (H2)** | 5.46 ms (mean) / 7.79 ms (p95) | **3.83 ms (mean) / 5.78 ms (p95)** | **1.4x Faster (In-Memory H2)** |
| **Projected Remote Network Latency (1ms RTT)** | ~56.46 ms | **~4.83 ms** | **11.7x Faster in Distributed Env** |
| **HikariCP Connection Pool Leases** | 51 connection requests | **1 connection lease** | Eliminates pool exhaustion |
| **Entities Hydrated** | 50 Users, 250 Orders | 50 Users, 250 Orders | 100% Data Integrity Preserved |
| **Surefire Test Suite** | 3 / 3 passed | **3 / 3 passed** | 100% Green Verification |

## Verification Evidence Reference
- Baseline SQL Log: `output/sql_log_before.txt` (51 queries: 1 root `users` select + 50 lazy `orders` selects)
- Optimized SQL Log: `output/sql_log_after.txt` (1 query: single `LEFT JOIN` hydration)
- Baseline Test Trace: `output/test_before_n1.txt`
- Optimized Test Trace: `output/test_after_fixed.txt`
- Applied Repository Patch: `fix.patch` / `output/fix.patch`
- Maven Surefire Report: `output/surefire_report.txt` / `output/TEST-com.ashfaq.n1.UserN1QueryTest.xml`
