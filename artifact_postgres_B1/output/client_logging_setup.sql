-- ============================================================================
-- Artifact B1: Non-Invasive PostgreSQL Production Logging Configuration
-- Target: PostgreSQL 13+ / 16+ / 18 (AWS RDS, Aurora, Cloud, Self-Hosted)
-- Description: Enables slow query profiling, checkpoint tracking, lock contention,
--              and disk temp file logging without requiring a database restart.
-- ============================================================================

-- 1. Set slow query logging threshold to 250 milliseconds.
-- Queries executing faster than 250ms are not logged, avoiding log volume churn.
ALTER SYSTEM SET log_min_duration_statement = 250;

-- 2. Audit checkpoint activity.
-- Logs checkpoint completion, distance, duration, buffer counts, and sync times.
ALTER SYSTEM SET log_checkpoints = 'on';

-- 3. Audit lock wait contention.
-- Logs when a query waits longer than deadlock_timeout (default 1s) to acquire a lock.
ALTER SYSTEM SET log_lock_waits = 'on';

-- 4. Audit temporary file disk spills.
-- Setting to 0 logs all temporary files created by sorts, hashes, and materializations,
-- providing forensic proof of insufficient work_mem.
ALTER SYSTEM SET log_temp_files = 0;

-- 5. Standard pgBadger compatible log line prefix.
-- Includes timestamp (%m), process ID (%p), user (%u), database (%d), and query tag (%q).
ALTER SYSTEM SET log_line_prefix = '%m [%p] %q%u@%d ';

-- 6. Audit autovacuum operations exceeding 250 milliseconds.
-- Identifies bloat cleanup stalls and long-running vacuum workers.
ALTER SYSTEM SET log_autovacuum_min_duration = 250;

-- 7. Apply configuration dynamically without restarting the server.
SELECT pg_reload_conf();

-- 8. Verification query to confirm runtime values across active settings.
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
