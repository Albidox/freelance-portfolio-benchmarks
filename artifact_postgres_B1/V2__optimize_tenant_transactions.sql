-- Production DDL Migration: V2__optimize_tenant_transactions.sql
-- Engine: PostgreSQL 13+
-- Risk Profile: Zero Downtime (CONCURRENTLY prevents exclusive table locks)

-- Prevent long lock queues from blocking live application traffic
SET lock_timeout = '5s';

-- Create composite covering index with INCLUDE clause
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenant_transactions_covering
ON tenant_transactions (tenant_id, created_at DESC)
INCLUDE (amount_cents);

-- Update query planner statistics
ANALYZE tenant_transactions;
