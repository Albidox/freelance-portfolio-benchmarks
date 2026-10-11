-- Artifact D11: PostgreSQL Index Creation Script
-- Baseline Full Composite Index vs Optimized Partial Index

-- Ensure clean setup if needed
-- DROP INDEX IF EXISTS d11_indexing_sandbox.idx_orders_composite_status_created;
-- DROP INDEX IF EXISTS d11_indexing_sandbox.idx_orders_partial_active_created;

-- 1. Baseline: Full Composite Index on (status, created_at DESC)
-- Indexes all 1,000,000 rows including COMPLETED and ARCHIVED records.
CREATE INDEX IF NOT EXISTS idx_orders_composite_status_created
ON d11_indexing_sandbox.orders (status, created_at DESC);

-- 2. Optimized: Partial Index on (created_at DESC) WHERE status = 'ACTIVE'
-- Indexes only the ~5% ACTIVE rows, dramatically reducing footprint and write amplification.
CREATE INDEX IF NOT EXISTS idx_orders_partial_active_created
ON d11_indexing_sandbox.orders (created_at DESC)
WHERE status = 'ACTIVE';

-- 3. Optimized: Expression Partial Index on JSONB document field
-- Indexes only urgent document flags, enabling sub-millisecond document query performance.
CREATE INDEX IF NOT EXISTS idx_orders_partial_urgent_jsonb
ON d11_indexing_sandbox.orders (created_at DESC)
WHERE ((metadata->>'urgent')::boolean = true);
