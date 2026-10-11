-- Production JSONB Optimization: V4__optimize_jsonb_queries.sql
-- Engine: PostgreSQL 13+
-- Risk Profile: Zero Downtime (CONCURRENTLY avoids blocking live writes)

SET lock_timeout = '5s';

-- Strategy 1: Functional Composite B-Tree Expression Index
-- Ideal for queries filtering on specific extracted key + sorting on timestamp
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_events_action_created
ON audit_events ((metadata->>'action_type'), created_at DESC);

-- Strategy 2: GIN jsonb_path_ops Index
-- Ideal for arbitrary multi-key JSON containment queries (@>)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_events_metadata_path_ops
ON audit_events USING gin (metadata jsonb_path_ops);

-- Update statistics for expression and GIN indexes
ANALYZE audit_events;
