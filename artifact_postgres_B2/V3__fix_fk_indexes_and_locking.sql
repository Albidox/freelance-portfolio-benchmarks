-- Production Concurrency & Deadlock Remediation: V3__fix_fk_indexes_and_locking.sql
-- Engine: PostgreSQL 13+
-- Risk Profile: Zero Downtime (CONCURRENTLY avoids table read/write locks)

SET lock_timeout = '5s';

-- 1. Index Unindexed Foreign Keys to prevent table-level share lock escalation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fk_reservations_product_id
ON inventory_reservations (product_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fk_line_items_reservation_id
ON order_line_items (reservation_id);

-- 2. Analyze updated planner statistics
ANALYZE inventory_reservations;
ANALYZE order_line_items;
