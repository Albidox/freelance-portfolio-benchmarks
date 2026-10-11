# Production PostgreSQL Parameter Tuning & Logging Audit Guide

**Author:** Sk Ashfaq Bux ([github.com/Albidox](https://github.com/Albidox))  
**Target:** PostgreSQL 13+ / 16+ / 18 (AWS RDS, Aurora, Cloud Managed, Dedicated Linux)  
**Specialization:** Database Performance Audits, Query Profiling, Indexing Architecture  

---

## 1. Executive Summary & Non-Invasive Tuning Philosophy

Optimizing high-throughput production databases requires strict empirical discipline. Applying speculative configuration changes or forcing database restarts during peak traffic introduces severe availability risks. A sound performance engineering protocol adheres to three invariants:

1. **Zero Downtime Profiling:** Diagnostic instrumentation must run non-invasively. Logging parameters must be reloaded dynamically (`SELECT pg_reload_conf()`) without terminating active client connections or requiring service restarts.
2. **Deterministic Memory Sizing:** Memory parameters such as `work_mem` and `maintenance_work_mem` must be derived from mathematical sizing formulae linked to connection limits and physical hardware. Under-allocation triggers disk spill degradation; over-allocation triggers Linux Out-Of-Memory (OOM) killer terminations.
3. **Safe Zero-Downtime Schema Evolution:** Index creation must never block production writes. Migrations must employ concurrent indexing guarded by strict lock timeouts to avoid catastrophic connection pooling backlogs.

This guide provides concrete configurations, architectural comparisons between AWS RDS and self-hosted deployments, safe migration patterns, and automated log analysis runbooks using pgBadger.

---

## 2. PostgreSQL Runtime Parameter Tuning Matrix & Formulae

The default configuration file (`postgresql.conf`) shipped with PostgreSQL is intentionally conservative, designed to run on systems with minimal RAM. Production backend infrastructure demands deliberate configuration aligned with modern NVMe storage and multi-core server architectures.

### 2.1 Memory Allocation & Buffer Architecture

```
+-----------------------------------------------------------------------+
| Total System RAM (e.g., 32 GB)                                        |
|                                                                       |
| +-------------------------+ +---------------------------------------+ |
| | shared_buffers (8 GB)   | | Operating System Page Cache (24 GB)   | |
| | (25% of Total RAM)      | | (Caches raw disk blocks, file buffers)| |
| +-------------------------+ +---------------------------------------+ |
|                                                                       |
| effective_cache_size = 24 GB (75% of Total RAM, informs planner)      |
+-----------------------------------------------------------------------+
                                    |
   Per-Connection / Per-Node Dynamic Memory Allocations
   +-----------------------------------------------------------------+
   | work_mem = (Total RAM - shared_buffers) / (max_connections * 3) |
   | Example: (32GB - 8GB) / (200 * 3) = 24,576 MB / 600 = ~40 MB    |
   +-----------------------------------------------------------------+
```

#### Sizing Rules:

1. **`shared_buffers = 25% of System RAM`**
   - **Baseline:** On dedicated Linux instances, set `shared_buffers` to 25% of total system memory (e.g., 8 GB on a 32 GB host).
   - **Rationale:** Allocating more than 40% often degrades performance due to double buffering overhead with the Linux page cache and increased checkpoint write serialization.
   - **AWS RDS Note:** AWS RDS sets default `shared_buffers` to `{DBInstanceClassMemory/4096}` (25% of instance RAM). Aurora PostgreSQL sets defaults up to 75% because its storage engine bypasses standard POSIX filesystem caching.

2. **`effective_cache_size = 75% of System RAM`**
   - **Baseline:** Set to 75% of total system memory (e.g., 24 GB on a 32 GB host).
   - **Rationale:** This setting does not allocate physical memory. It provides the query planner with a realistic estimate of the memory available for caching table and index pages (combining `shared_buffers` and the kernel page cache). A higher estimate encourages index scans over sequential scans.

3. **`work_mem`: The Concurrency Sizing Formula**
   - **Risk:** Setting `work_mem` too low forces sort operations, hash joins, and aggregations to spill to disk, multiplying query latency by 10x to 50x. Setting it too high exposes the cluster to Linux OOM killer invocation (`SIGKILL` sent to PostgreSQL postmaster child processes).
   - **The Sizing Formula:**
     ```
     work_mem = (Total RAM - shared_buffers) / (max_connections * concurrent_operations_per_query)
     ```
   - **Multiplier Invariant:** A single complex query can allocate `work_mem` across multiple execution nodes (e.g., three separate sort and hash join operations). Furthermore, when parallel query execution is active, each parallel worker (`max_parallel_workers_per_gather`) allocates its own `work_mem`. Using a multiplier of `3` provides a robust safety margin.
   - **Worked Example (32 GB RAM, 200 Max Connections):**
     - Available Memory: `32 GB - 8 GB = 24 GB = 24,576 MB`
     - Maximum Operations: `200 * 3 = 600`
     - Calculation: `24,576 MB / 600 = 40.96 MB`
     - Conservative Production Setting: `32 MB` (or `40 MB`)
   - **Analytical Session Override:** Never set global `work_mem` to gigabyte levels for the entire cluster. Instead, grant targeted memory overrides to specific batch ETL sessions:
     ```sql
     -- Executed only within the analytical migration or batch session
     SET work_mem = '256MB';
     ```

4. **`maintenance_work_mem = 5% to 10% of System RAM (Capped at 2 GB)`**
   - **Baseline:** 1 GB to 2 GB on modern instances.
   - **Rationale:** Allocates memory for maintenance workers executing `VACUUM`, `CREATE INDEX`, and `ALTER TABLE ADD FOREIGN KEY`. Because maintenance tasks run sequentially or under strict worker limits (`autovacuum_max_workers`), higher values drastically reduce index construction times.

5. **`wal_buffers = 16MB`**
   - **Baseline:** 16 MB (or 1/32 of `shared_buffers`, capped at 64 MB).
   - **Rationale:** Buffers unwritten WAL records in memory prior to disk flush. 16 MB is sufficient to absorb heavy transaction write bursts.

---

### 2.2 Storage Engine & Planner Cost Optimization

| Configuration Parameter | Default (Legacy HDD) | Production (NVMe / SSD / EBS gp3) | Architectural Rationale |
|---|---|---|---|
| `seq_page_cost` | `1.0` | `1.0` | Arbitrary benchmark baseline for sequential disk block reads. |
| `random_page_cost` | `4.0` | `1.1` | Default `4.0` reflects 7,200 RPM rotational disk seek latency. On NVMe and SSD storage, random block access latency is virtually identical to sequential access. Leaving this at `4.0` causes the planner to erroneously select sequential scans over B-Tree index scans. |
| `effective_io_concurrency` | `1` | `200` | Controls asynchronous prefetch depth. Allows PostgreSQL to issue multiple concurrent read requests to the underlying NVMe storage controller or AWS EBS volume. |
| `default_statistics_target` | `100` | `100` (up to `500` for skewed keys) | Determines catalog sample depth for histogram generation. Increasing to `500` on high-skew multi-tenant keys resolves planner misestimations. |

---

### 2.3 Checkpoint Spreading & Write-Ahead Log (WAL) Tuning

Frequent checkpoints cause write amplification and CPU spikes. Properly tuned checkpoints spread I/O smoothly over time.

```sql
-- Spread checkpoint writes over 90% of the checkpoint duration
checkpoint_completion_target = 0.9

-- Extend checkpoint window to 15 minutes to reduce checkpoint write frequency
checkpoint_timeout = 15min

-- Maintain adequate WAL retention to prevent premature forced checkpoints
min_wal_size = 2GB
max_wal_size = 16GB
```

---

## 3. Non-Invasive Production Logging Configuration

Forensic database audits require capturing high-latency queries, disk spills, lock waits, and checkpoint activity without restarting the database.

### 3.1 Parameter Reference

1. **`log_min_duration_statement = 250` (milliseconds)**
   - Captures any statement taking longer than 250 ms.
   - Setting to 0 logs every statement (creates severe I/O overhead in production). Setting to -1 disables logging. 250 ms isolates latency outliers without log volume flooding.
2. **`log_checkpoints = on`**
   - Emits log records when checkpoints start and finish, detailing write duration, buffer write counts, and sync times. Essential for diagnosing storage write saturation.
3. **`log_lock_waits = on`**
   - Logs when a session waits longer than `deadlock_timeout` (default 1 second) to acquire a lock. Crucial for tracing transaction queue cascades.
4. **`log_temp_files = 0` (bytes)**
   - Logs every temporary file created when queries spill sorts or hash tables to disk. Setting to `0` logs all temporary file spills along with statement text and file size.
5. **`log_autovacuum_min_duration = 250` (milliseconds)**
   - Logs autovacuum actions taking longer than 250 ms, pinpointing table bloat and freezing stalls.
6. **`log_line_prefix = '%m [%p] %q%u@%d '`**
   - Standard prefix required by pgBadger:
     - `%m`: Timestamp with milliseconds.
     - `%p`: Process ID.
     - `%q`: Query cancel/empty separator.
     - `%u`: Authenticated database user.
     - `%d`: Target database name.

### 3.2 Non-Invasive Execution Script (`client_logging_setup.sql`)

Clients can execute this script directly in `psql` or their database administration console. It applies parameter changes via `ALTER SYSTEM` and reloads the engine dynamically using `SELECT pg_reload_conf()`. Zero database restarts are required:

```sql
-- ============================================================================
-- Artifact B1: Non-Invasive PostgreSQL Production Logging Configuration
-- Target: PostgreSQL 13+ / 16+ / 18 (AWS RDS, Aurora, Cloud, Self-Hosted)
-- ============================================================================

-- 1. Slow query duration threshold (250ms)
ALTER SYSTEM SET log_min_duration_statement = 250;

-- 2. Audit checkpoint activity
ALTER SYSTEM SET log_checkpoints = 'on';

-- 3. Audit lock wait contention
ALTER SYSTEM SET log_lock_waits = 'on';

-- 4. Audit temporary disk spills (0 captures all spills)
ALTER SYSTEM SET log_temp_files = 0;

-- 5. Standard pgBadger compatible log line prefix
ALTER SYSTEM SET log_line_prefix = '%m [%p] %q%u@%d ';

-- 6. Audit autovacuum operations exceeding 250ms
ALTER SYSTEM SET log_autovacuum_min_duration = 250;

-- 7. Apply configuration dynamically without restarting the server
SELECT pg_reload_conf();

-- 8. Verify active settings from system catalog
SELECT name, setting, unit, source
FROM pg_settings
WHERE name IN (
    'log_min_duration_statement',
    'log_checkpoints',
    'log_lock_waits',
    'log_temp_files',
    'log_line_prefix',
    'log_autovacuum_min_duration'
);
```

---

## 4. AWS RDS / Aurora vs Self-Hosted PostgreSQL Differences

Managing database parameters and log aggregation differs substantially between managed cloud services and self-hosted Linux instances.

```
+-----------------------------------------------------------------------------+
| Architectural Comparison: Configuration & Log Ingestion                      |
+-----------------------------------------------------------------------------+
| Feature                   | AWS RDS / Aurora           | Self-Hosted Linux  |
+---------------------------+----------------------------+--------------------+
| Configuration Layer       | DB Parameter Group         | postgresql.conf    |
| Parameter Application     | AWS CLI / RDS Console      | ALTER SYSTEM / CLI |
| Static Parameter Changes  | Requires Instance Reboot   | Requires pg_ctl    |
| Dynamic Parameter Changes | Apply Immediately          | pg_reload_conf()   |
| Log Destination           | CloudWatch Logs / RDS Disk | /var/log/postgres/ |
| Log Rotation              | AWS Managed                | logrotate / engine |
| Autovacuum Logging Override| rds.force_autovacuum_...  | Native engine flag |
| Connection Pooling        | RDS Proxy (Managed)        | PgBouncer / Native |
+-----------------------------------------------------------------------------+
```

### 4.1 Parameter Management & Lifecycle

- **Self-Hosted Linux:**
  - Parameters reside in `/etc/postgresql/<version>/main/postgresql.conf` or `postgresql.auto.conf`.
  - Dynamic parameters reload instantly via `SELECT pg_reload_conf();` or terminal command `pg_ctl reload -D $PGDATA` (sending `SIGHUP`).
  - Static parameters (such as `shared_buffers`, `max_connections`, `wal_level`) require a controlled daemon restart (`systemctl restart postgresql`).

- **AWS RDS & Aurora:**
  - Parameters are abstracted into **DB Parameter Groups**.
  - Parameters have an explicit `ApplyType`:
    - `dynamic`: Applies immediately upon parameter group modification when `ApplyImmediately=true` is specified.
    - `static`: Marked as `pending-reboot`. Takes effect only after an explicit manual DB instance reboot.
  - AWS CLI Modification Command:
    ```bash
    aws rds modify-db-parameter-group \
        --db-parameter-group-name custom-postgres16-prod \
        --parameters "ParameterName=log_min_duration_statement,ParameterValue=250,ApplyMethod=immediate" \
                     "ParameterName=log_checkpoints,ParameterValue=1,ApplyMethod=immediate" \
                     "ParameterName=log_lock_waits,ParameterValue=1,ApplyMethod=immediate" \
                     "ParameterName=log_temp_files,ParameterValue=0,ApplyMethod=immediate" \
                     "ParameterName=random_page_cost,ParameterValue=1.1,ApplyMethod=immediate"
    ```

### 4.2 Cloud Logging Architecture

- **AWS RDS Log Export:**
  - Configure RDS to stream log events directly to AWS CloudWatch Logs by enabling the `postgresql` log export:
    ```bash
    aws rds modify-db-instance \
        --db-instance-identifier prod-db-instance \
        --cloudwatch-logs-exports-configuration '{"Enable":["postgresql"]}' \
        --apply-immediately
    ```
  - For autovacuum audit tracking in RDS, ensure the parameter group includes:
    ```text
    rds.force_autovacuum_logging_level = 'log'
    ```

- **Log Retrieval for Auditing:**
  - Download active log slices directly via AWS CLI for pgBadger profiling:
    ```bash
    aws rds download-db-log-file-portion \
        --db-instance-identifier prod-db-instance \
        --log-file-name error/postgresql.log \
        --output text > rds_postgres.log
    ```

### 4.3 Connection Pooling & `work_mem` Interaction

In unpooled environments, applications frequently spawn 500 to 1,000 direct connections. Under this model, `work_mem` must be restricted to tiny values (2 MB to 4 MB) to prevent out-of-memory crashes.

By introducing connection poolers (AWS RDS Proxy for AWS, or self-hosted PgBouncer in transaction pooling mode):
- Server-side active backend connections drop from 1,000 down to 50 or 100.
- `max_connections` in PostgreSQL can be safely lowered to 100.
- `work_mem` can be expanded from 4 MB to 64 MB per operation, completely eliminating disk spills without increasing total system RAM consumption.

---

## 5. Safe Zero-Downtime Index Migration Rules

Adding indexes to active production tables is one of the most hazardous schema operations if executed incorrectly.

### 5.1 The Dangers of Standard `CREATE INDEX`

Standard `CREATE INDEX` executes with an exclusive table lock:
- Acquires a `SHARE` lock on the target table.
- Blocks all concurrent write transactions (`INSERT`, `UPDATE`, `DELETE`).
- Reads (`SELECT`) continue to function, but any new write transaction blocks immediately.
- Subsequent `SELECT` queries that require read locks on rows modified by blocked transactions queue up behind the blocked writes.
- Within seconds, application connection pools saturate, resulting in cluster-wide HTTP 504 gateway timeouts.

### 5.2 Anatomy of `CREATE INDEX CONCURRENTLY`

`CREATE INDEX CONCURRENTLY` bypasses table-level write blocking:
- Acquires a weak `SHARE UPDATE EXCLUSIVE` lock.
- Permits simultaneous reads and writes (`SELECT`, `INSERT`, `UPDATE`, and `DELETE` remain unblocked).
- Executes two sequential full table scans:
  1. **Scan 1 (Initial Build):** Scans the heap, builds the index leaf structure, and registers the index in the catalog with status `in progress`.
  2. **Scan 2 (Validation):** Scans the heap a second time to resolve and index any tuple insertions, updates, or deletions that occurred during Scan 1.
- Completes by marking the index valid and active for the query planner.

### 5.3 Critical Operational Caveats & Failure Modes

#### Caveat 1: Transaction Block Restriction
`CREATE INDEX CONCURRENTLY` **cannot** run inside an explicit transaction block (`BEGIN ... COMMIT`).
- Standard database migration tools (Flyway, Liquibase) default to wrapping each migration script in an atomic transaction block.
- For Flyway, the migration must be marked out-of-transaction or set `mixed = true`.
- For Liquibase, use `<changeSet ... runInTransaction="false">`.

#### Caveat 2: The Invalid Index Trap
If a concurrent index build terminates prematurely due to a client disconnect, statement timeout, deadlock, or unique key violation:
- PostgreSQL marks the index as `INVALID` in `pg_index` (`indisvalid = false`).
- **The Catastrophe:** The query planner will **never** use an invalid index to accelerate queries. However, because the physical index exists, every subsequent `INSERT`, `UPDATE`, and `DELETE` on the table is still forced to update the invalid index structure.
- Leaving invalid indexes on a high-write table degrades write throughput while providing zero read acceleration.

#### Remediation & Detection Script:
Always inspect the catalog for invalid indexes:

```sql
-- Audit query: Detect invalid indexes across the database
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    i.relname AS index_name,
    x.indisvalid AS is_valid
FROM pg_index x
JOIN pg_class c ON c.oid = x.indrelid
JOIN pg_class i ON i.oid = x.indexrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE NOT x.indisvalid;
```

If an invalid index is detected, remove it concurrently and rebuild:

```sql
-- Safe cleanup of failed concurrent build
DROP INDEX CONCURRENTLY IF EXISTS idx_tenant_transactions_covering;

-- Rebuild with proper timeouts
SET lock_timeout = '5s';
CREATE INDEX CONCURRENTLY idx_tenant_transactions_covering
ON tenant_transactions (tenant_id, created_at DESC)
INCLUDE (amount_cents);
```

### 5.4 Mandatory Migration Guardrails

Before running a concurrent index build, enforce strict session guardrails:

```sql
-- Guardrail 1: Abort if lock acquisition waits longer than 5 seconds.
-- Prevents the migration session from queueing up behind long-running analytical queries.
SET lock_timeout = '5s';

-- Guardrail 2: Disable statement timeout for the migration session.
-- Ensures large table builds (tens of millions of rows) are not killed mid-execution.
SET statement_timeout = '0';

-- Guardrail 3: Boost maintenance memory for the current migration session.
SET maintenance_work_mem = '2GB';

-- Guardrail 4: Concurrent index execution
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenant_transactions_covering
ON tenant_transactions (tenant_id, created_at DESC)
INCLUDE (amount_cents);

-- Guardrail 5: Refresh catalog statistics immediately
ANALYZE tenant_transactions;
```

---

## 6. Runbook: Reproducing, Profiling, and Auditing with pgBadger

pgBadger is the industry-standard log analysis engine for PostgreSQL. It compiles gigabytes of raw stderr or CSV logs into standalone, interactive HTML reports with latency percentiles, lock wait timelines, and temporary file histograms.

### Step 1: Apply Logging Configuration
Execute the non-invasive configuration script against the target database:

```bash
psql -h 127.0.0.1 -p 5433 -U postgres -f client_logging_setup.sql
```

Confirm that `log_line_prefix` matches `%m [%p] %q%u@%d `.

### Step 2: Verify Configuration Status
Verify that settings are active in the system catalog:

```sql
SELECT name, setting, unit, source
FROM pg_settings
WHERE name IN ('log_min_duration_statement', 'log_line_prefix', 'log_temp_files');
```

### Step 3: Exercise Workload (Simulate Queries and Temp Disk Spills)
Execute production queries or synthetic benchmark suites. Any statement exceeding 250 ms or spilling to disk will be logged:

```bash
psql -h 127.0.0.1 -p 5433 -U postgres -f broken_query.sql
```

### Step 4: Compile pgBadger Forensic HTML Report
Execute pgBadger pointing to the PostgreSQL log file. Ensure the `--prefix` argument matches `log_line_prefix` exactly:

```bash
pgbadger \
    --prefix '%m [%p] %q%u@%d ' \
    -f stderr \
    --jobs 4 \
    --outfile pgbadger_report.html \
    /path/to/postgresql.log
```

### Step 5: Metric Interpretation Guide

When reviewing the compiled `pgbadger_report.html`, focus on four critical diagnostic panels:

1. **Top Slowest Queries (Normalized):**
   - Identifies queries consuming the greatest cumulative execution time across the cluster.
   - Cross-reference with `EXPLAIN (ANALYZE, BUFFERS)` to diagnose missing indexes or sequential scan regressions.
2. **Temporary Files Generated (Disk Spills):**
   - Inspect the `Temporary Files` section for queries creating large disk buffers (e.g., `152 kB` to hundreds of megabytes).
   - Direct indicator that `work_mem` is insufficient for the query's sort or hash join operations.
3. **Lock Wait Timeline:**
   - Tracks timestamp spikes where queries waited for table or row locks.
   - Correlate with concurrent DDL operations, batch updates, or unindexed foreign keys causing share locks on parent tables.
4. **Checkpoint Activity:**
   - Shows checkpoint duration and distance.
   - If checkpoints occur continuously at intervals under 5 minutes with high buffer write counts, increase `checkpoint_timeout` and `max_wal_size`.

---

## 7. Production Verification & Audit Checklist

Before signing off on any production PostgreSQL optimization or migration, verify every item on this checklist:

- [ ] **Dynamic Configuration:** All logging flags (`log_min_duration_statement`, `log_checkpoints`, `log_lock_waits`, `log_temp_files`) were applied dynamically without a database restart.
- [ ] **Memory Safety Formula:** `work_mem` is mathematically bounded using `(Total RAM - shared_buffers) / (max_connections * 3)` to prevent Linux OOM terminations.
- [ ] **Storage Cost Alignment:** `random_page_cost` is tuned to `1.1` on SSD/NVMe/gp3 volumes, matching storage reality.
- [ ] **Safe Schema Evolution:** All new indexes were created using `CREATE INDEX CONCURRENTLY` outside of explicit transaction blocks.
- [ ] **Lock Timeout Safety:** All migration sessions enforce `SET lock_timeout = '5s'` to prevent queuing locks behind ongoing traffic.
- [ ] **Zero Invalid Indexes:** The catalog was audited (`WHERE NOT indisvalid`) confirming zero broken index artifacts remain.
- [ ] **Observable Verification:** Pre- and post-optimization query plans (`EXPLAIN (ANALYZE, BUFFERS)`) confirm access method shifts from heap scans to Index Only Scans with zero heap fetches and zero temp spills.
