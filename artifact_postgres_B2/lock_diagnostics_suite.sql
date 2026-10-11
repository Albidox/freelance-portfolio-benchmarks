-- ==============================================================================
-- Artifact B2-R2: Real-Time PostgreSQL Lock Diagnostic Toolkit
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Active Blocking Queries Inspector
-- ------------------------------------------------------------------------------
-- Identifies queries that are currently blocked and the queries blocking them.
-- Uses explicit joins between pg_stat_activity and pg_locks for detailed lock types.
SELECT
    blocked_locks.pid     AS blocked_pid,
    blocked_activity.usename  AS blocked_user,
    blocking_locks.pid     AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_locks.mode    AS lock_mode_requested,
    blocked_activity.query    AS blocked_statement,
    blocking_activity.query   AS current_statement_in_blocking_process
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- ------------------------------------------------------------------------------
-- 2. Lock Wait Hierarchy Tree
-- ------------------------------------------------------------------------------
-- Displays a hierarchical view of who is blocking whom, useful for deep lock chains.
WITH RECURSIVE lock_tree AS (
    SELECT
        blocked_activity.pid AS blocked_pid,
        blocking_activity.pid AS blocker_pid,
        blocked_locks.mode AS lock_mode,
        now() - blocked_activity.state_change AS wait_duration,
        blocked_activity.query,
        1 AS depth,
        ARRAY[blocked_activity.pid] AS path
    FROM pg_catalog.pg_locks blocked_locks
    JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
    JOIN pg_catalog.pg_locks blocking_locks 
        ON blocking_locks.locktype = blocked_locks.locktype
        AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
        AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
        AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
        AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
        AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
        AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
        AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
        AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
        AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
        AND blocking_locks.pid != blocked_locks.pid
    JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
    WHERE NOT blocked_locks.granted
    AND blocking_activity.pid NOT IN (
        SELECT pid FROM pg_catalog.pg_locks WHERE NOT granted
    )
    UNION ALL
    SELECT
        blocked_activity.pid AS blocked_pid,
        blocking_activity.pid AS blocker_pid,
        blocked_locks.mode AS lock_mode,
        now() - blocked_activity.state_change AS wait_duration,
        blocked_activity.query,
        t.depth + 1,
        t.path || blocked_activity.pid AS path
    FROM pg_catalog.pg_locks blocked_locks
    JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
    JOIN pg_catalog.pg_locks blocking_locks 
        ON blocking_locks.locktype = blocked_locks.locktype
        AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
        AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
        AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
        AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
        AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
        AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
        AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
        AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
        AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
        AND blocking_locks.pid != blocked_locks.pid
    JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
    JOIN lock_tree t ON t.blocked_pid = blocking_activity.pid
    WHERE NOT blocked_locks.granted
    AND blocked_activity.pid != ANY(t.path)
)
SELECT
    lpad('', (depth - 1) * 2, ' ') || blocked_pid::text AS blocked_pid_tree,
    blocked_pid,
    blocker_pid,
    lock_mode,
    wait_duration,
    query
FROM lock_tree
ORDER BY path;

-- ------------------------------------------------------------------------------
-- 3. Unindexed Foreign Keys Discovery Query
-- ------------------------------------------------------------------------------
-- Queries pg_constraint vs pg_index to find every naked (unindexed) FK in the schema.
-- Unindexed FKs cause severe lock contention and table scans during parent deletes/updates.
SELECT 
    c.conrelid::regclass AS table_name,
    c.conname AS constraint_name,
    pg_get_constraintdef(c.oid) AS fk_definition
FROM pg_constraint c
WHERE c.contype = 'f'
  AND NOT EXISTS (
    SELECT 1
    FROM pg_index i
    WHERE i.indrelid = c.conrelid
      -- The index must start with the exact columns used in the FK
      AND (i.indkey::int2[])[1:array_length(c.conkey, 1)] = c.conkey::int2[]
  )
ORDER BY table_name, constraint_name;

-- ------------------------------------------------------------------------------
-- 4. Safe Emergency Transaction Termination Query
-- ------------------------------------------------------------------------------
-- Identifies long-running active or idle-in-transaction sessions, 
-- and generates the exact SQL commands to cancel the query or terminate the connection safely.
SELECT
    pid,
    usename,
    application_name,
    client_addr,
    state,
    now() - state_change AS duration,
    query,
    -- Safe cancellation: Cancels only the current query, leaving the connection intact.
    'SELECT pg_cancel_backend(' || pid || ');' AS safe_cancel_command,
    -- Emergency termination: Forcefully closes the connection. Use only if cancel fails.
    'SELECT pg_terminate_backend(' || pid || ');' AS emergency_terminate_command
FROM pg_stat_activity
WHERE pid <> pg_backend_pid()
  AND (
       (state = 'active' AND now() - state_change > interval '1 minute')
    OR (state LIKE 'idle in transaction%' AND now() - state_change > interval '5 minutes')
  )
ORDER BY duration DESC;
