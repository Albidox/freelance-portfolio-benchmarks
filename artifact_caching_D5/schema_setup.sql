-- Schema setup script for Artifact D5: Caching Layer Integration
-- Target: PostgreSQL 18 on port 5433
-- Schema: d5_caching_sandbox

CREATE SCHEMA IF NOT EXISTS d5_caching_sandbox;

SET search_path TO d5_caching_sandbox, public;

DROP TABLE IF EXISTS d5_caching_sandbox.products CASCADE;

CREATE TABLE d5_caching_sandbox.products (
    id BIGSERIAL PRIMARY KEY,
    sku VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100) NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    manufacturer VARCHAR(100) DEFAULT 'Enterprise Corp',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_products_sku ON d5_caching_sandbox.products (sku);
CREATE INDEX idx_products_category ON d5_caching_sandbox.products (category);

-- Seed 5,000 products with realistic catalog data
INSERT INTO d5_caching_sandbox.products (sku, name, description, category, price, stock_quantity, created_at, updated_at)
SELECT
    'PROD-' || LPAD(i::text, 5, '0') AS sku,
    'Enterprise Cloud Module ' || i AS name,
    'High throughput distributed computing node with specification tier ' || (i % 10 + 1) AS description,
    CASE (i % 5)
        WHEN 0 THEN 'Hardware'
        WHEN 1 THEN 'Networking'
        WHEN 2 THEN 'Storage'
        WHEN 3 THEN 'Compute'
        ELSE 'Security'
    END AS category,
    ROUND((29.99 + (i * 0.47) % 970.00)::numeric, 2) AS price,
    (50 + (i * 13) % 450)::integer AS stock_quantity,
    CURRENT_TIMESTAMP - (i || ' minutes')::interval AS created_at,
    CURRENT_TIMESTAMP - (i || ' minutes')::interval AS updated_at
FROM generate_series(1, 5000) AS s(i);

-- Verification count
SELECT count(*) AS total_products FROM d5_caching_sandbox.products;
