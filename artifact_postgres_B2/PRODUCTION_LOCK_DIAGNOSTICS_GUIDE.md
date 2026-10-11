# PostgreSQL Production Lock Diagnostics Guide

## Overview
This toolkit provides real-time emergency diagnostics for PostgreSQL lock contention, blocking queries, and transaction state. It is designed to be safely run directly against a production database during an outage to quickly identify root causes without impacting the system further.

## Usage

During an incident, execute `lock_diagnostics_suite.sql` via `psql` or run the queries individually from your SQL client.

```bash
psql -U postgres -h localhost -p 5433 -d mydatabase -f lock_diagnostics_suite.sql
```

## Toolkit Breakdown

### 1. Active Blocking Queries Inspector
**Purpose:** Identifies exact queries that are blocked, which user/process is blocking them, and the lock mode requested.
**When to use:** When application dashboards report high latency or timeouts, and you suspect database-level blocking.
**Actionable Insight:** Look for `current_statement_in_blocking_process`. This is the query holding the lock. If it's an `idle in transaction`, the application may have leaked a connection or failed to commit/rollback.

### 2. Lock Wait Hierarchy Tree
**Purpose:** Visualizes deep chains of locks (e.g., A blocks B, B blocks C).
**When to use:** During severe outages ("lock storms") where hundreds of connections pile up.
**Actionable Insight:** Focus on the root blocker (the top level of the tree, `depth = 1`). Resolving the root blocker will typically unblock the entire cascade.

### 3. Unindexed Foreign Keys Discovery Query
**Purpose:** Identifies "naked" (unindexed) foreign keys across the schema.
**When to use:** Proactively during schema reviews, or reactively when `DELETE` or `UPDATE` operations on parent tables are extremely slow or causing lock contention on child tables.
**Actionable Insight:** In PostgreSQL, modifying or deleting rows in a parent table requires a ShareLock on the child table to ensure referential integrity. If the child table lacks an index on the foreign key column, Postgres must perform a full sequential scan on the child table while holding the lock. Create indexes on all discovered columns immediately.

### 4. Safe Emergency Transaction Termination Query
**Purpose:** Finds long-running or stalled connections and generates safe commands to terminate them.
**When to use:** When you have identified a blocking PID (from Query 1 or 2) that needs to be killed to restore service.
**Actionable Insight:** 
- Always try the `safe_cancel_command` (`pg_cancel_backend`) first. This sends a SIGINT and allows the query to gracefully roll back without breaking the client connection.
- If the backend is stuck and does not respond to cancellation, use the `emergency_terminate_command` (`pg_terminate_backend`) to send a SIGTERM and kill the connection outright.
