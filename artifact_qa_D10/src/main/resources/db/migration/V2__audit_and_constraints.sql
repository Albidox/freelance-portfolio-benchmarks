-- V2: Audit logging table and indexes.
-- Strict zero em dashes policy enforced.

CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id BIGINT NOT NULL,
    action VARCHAR(50) NOT NULL,
    details TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

COMMENT ON TABLE customers IS 'Customer account records';
COMMENT ON TABLE products IS 'Product catalog with inventory counts';
COMMENT ON TABLE orders IS 'Customer orders with status lifecycle';
COMMENT ON TABLE order_items IS 'Individual order line items';
COMMENT ON TABLE audit_logs IS 'System audit history';
