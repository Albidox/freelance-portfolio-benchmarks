-- Rollback Concurrency & Deadlock Remediation: rollback_V3.sql

SET lock_timeout = '5s';

DROP INDEX CONCURRENTLY IF EXISTS idx_fk_reservations_product_id;
DROP INDEX CONCURRENTLY IF EXISTS idx_fk_line_items_reservation_id;
