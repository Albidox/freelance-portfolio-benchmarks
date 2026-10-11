-- Rollback Script: rollback.sql
-- Safely drop indexes concurrently

DROP INDEX CONCURRENTLY IF EXISTS idx_audit_events_action_created;
DROP INDEX CONCURRENTLY IF EXISTS idx_audit_events_metadata_path_ops;
