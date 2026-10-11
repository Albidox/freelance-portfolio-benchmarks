-- Rollback Migration: rollback_V2.sql
-- Engine: PostgreSQL 13+
-- Risk Profile: Zero Downtime (CONCURRENTLY prevents exclusive table locks)

SET lock_timeout = '5s';

DROP INDEX CONCURRENTLY IF EXISTS idx_tenant_transactions_covering;
DROP INDEX CONCURRENTLY IF EXISTS idx_tenant_transactions_perf;
