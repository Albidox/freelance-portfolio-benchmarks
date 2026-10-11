-- PostgreSQL Bloat and Dead Tuple Diagnostic Query
-- Schema: d15_vacuum_sandbox
-- Target: orders table and associated indexes

WITH raw_table_stats AS (
    SELECT
        s.schemaname,
        s.relname,
        c.oid AS table_oid,
        s.n_live_tup,
        s.n_dead_tup,
        c.reltuples,
        pg_relation_size(c.oid) AS table_size_bytes,
        pg_indexes_size(c.oid) AS indexes_size_bytes,
        pg_total_relation_size(c.oid) AS total_size_bytes,
        s.last_vacuum,
        s.last_autovacuum,
        s.last_analyze,
        -- Extract table-level autovacuum overrides if configured, else fallback to global settings
        COALESCE(
            (SELECT (regexp_matches(val, 'autovacuum_vacuum_scale_factor=([0-9.]+)'))[1]::numeric
             FROM unnest(c.reloptions) AS val
             WHERE val LIKE 'autovacuum_vacuum_scale_factor%'),
            current_setting('autovacuum_vacuum_scale_factor')::numeric
        ) AS vacuum_scale_factor,
        COALESCE(
            (SELECT (regexp_matches(val, 'autovacuum_vacuum_threshold=([0-9]+)'))[1]::numeric
             FROM unnest(c.reloptions) AS val
             WHERE val LIKE 'autovacuum_vacuum_threshold%'),
            current_setting('autovacuum_vacuum_threshold')::numeric
        ) AS vacuum_threshold
    FROM pg_stat_user_tables s
    JOIN pg_class c ON c.oid = s.relid
    WHERE s.schemaname = 'd15_vacuum_sandbox'
      AND s.relname = 'orders'
)
SELECT
    schemaname,
    relname,
    n_live_tup,
    n_dead_tup,
    CASE 
        WHEN (n_live_tup + n_dead_tup) > 0 
        THEN ROUND((n_dead_tup::numeric / (n_live_tup + n_dead_tup)::numeric) * 100, 2)
        ELSE 0.00
    END AS dead_tuple_ratio_pct,
    pg_size_pretty(table_size_bytes) AS table_size_pretty,
    pg_size_pretty(indexes_size_bytes) AS indexes_size_pretty,
    pg_size_pretty(total_size_bytes) AS total_size_pretty,
    table_size_bytes,
    indexes_size_bytes,
    total_size_bytes,
    ROUND(
        CASE 
            WHEN (n_live_tup + n_dead_tup) > 0 
            THEN table_size_bytes * (n_dead_tup::numeric / (n_live_tup + n_dead_tup)::numeric)
            ELSE 0
        END
    ) AS estimated_wasted_table_bytes,
    pg_size_pretty(
        ROUND(
            CASE 
                WHEN (n_live_tup + n_dead_tup) > 0 
                THEN table_size_bytes * (n_dead_tup::numeric / (n_live_tup + n_dead_tup)::numeric)
                ELSE 0
            END
        )
    ) AS estimated_wasted_table_pretty,
    vacuum_threshold AS configured_threshold,
    vacuum_scale_factor AS configured_scale_factor,
    ROUND(vacuum_threshold + (vacuum_scale_factor * GREATEST(n_live_tup, reltuples::bigint))) AS autovacuum_trigger_threshold,
    ROUND(n_dead_tup - (vacuum_threshold + (vacuum_scale_factor * GREATEST(n_live_tup, reltuples::bigint)))) AS threshold_deficit,
    CASE 
        WHEN n_dead_tup >= (vacuum_threshold + (vacuum_scale_factor * GREATEST(n_live_tup, reltuples::bigint)))
        THEN true 
        ELSE false 
    END AS autovacuum_due,
    last_vacuum,
    last_autovacuum,
    last_analyze
FROM raw_table_stats;
