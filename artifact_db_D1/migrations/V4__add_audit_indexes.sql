-- V4: Create partial index on active orders
-- Author: Eric (Ashfaq Lead Software Engineering Specialist)

CREATE INDEX IF NOT EXISTS idx_orders_active_recent
ON orders (created_at DESC)
WHERE status IN ('PENDING', 'PROCESSING', 'ACTIVE');
