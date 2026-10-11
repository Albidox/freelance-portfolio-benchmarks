DROP TABLE IF EXISTS order_line_items CASCADE;
DROP TABLE IF EXISTS inventory_reservations CASCADE;
DROP TABLE IF EXISTS products CASCADE;

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    stock_count INTEGER NOT NULL DEFAULT 500,
    price_cents INTEGER NOT NULL
);

CREATE TABLE inventory_reservations (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id), -- Intentionally unindexed FK
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE order_line_items (
    id SERIAL PRIMARY KEY,
    reservation_id INTEGER NOT NULL REFERENCES inventory_reservations(id), -- Intentionally unindexed FK
    order_id UUID NOT NULL DEFAULT gen_random_uuid(),
    price_cents INTEGER NOT NULL
);

-- Seed 1,000 products
INSERT INTO products (name, stock_count, price_cents)
SELECT 'Product SKU-' || g, 1000, (random() * 5000 + 500)::int
FROM generate_series(1, 1000) AS g;

-- Seed 50,000 reservations
INSERT INTO inventory_reservations (product_id, quantity, status)
SELECT (random() * 999 + 1)::int, (random() * 5 + 1)::int, 'PENDING'
FROM generate_series(1, 50000) AS g;

-- Seed 100,000 line items
INSERT INTO order_line_items (reservation_id, price_cents)
SELECT (random() * 49999 + 1)::int, (random() * 5000 + 500)::int
FROM generate_series(1, 100000) AS g;

ANALYZE products;
ANALYZE inventory_reservations;
ANALYZE order_line_items;
