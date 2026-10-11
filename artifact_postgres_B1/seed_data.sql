CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DROP TABLE IF EXISTS tenant_transactions CASCADE;

CREATE TABLE tenant_transactions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    amount_cents INTEGER NOT NULL,
    description TEXT
);

-- Seed 500,000 rows across 10 tenant UUIDs with timestamps spanning 365 days
SET synchronous_commit = 'off';

INSERT INTO tenant_transactions (tenant_id, created_at, amount_cents, description)
SELECT
    (ARRAY[
        'a1b2c3d4-0000-0000-0000-000000000001',
        'a1b2c3d4-0000-0000-0000-000000000002',
        'a1b2c3d4-0000-0000-0000-000000000003',
        'a1b2c3d4-0000-0000-0000-000000000004',
        'a1b2c3d4-0000-0000-0000-000000000005',
        'a1b2c3d4-0000-0000-0000-000000000006',
        'a1b2c3d4-0000-0000-0000-000000000007',
        'a1b2c3d4-0000-0000-0000-000000000008',
        'a1b2c3d4-0000-0000-0000-000000000009',
        'a1b2c3d4-0000-0000-0000-000000000010'
    ]::uuid[])[(random() * 9 + 1)::int],
    NOW() - (random() * 365 * INTERVAL '1 day'),
    (random() * 100000 + 100)::int,
    'Transactional Ledger Entry #' || g
FROM generate_series(1, 500000) AS g;

SET synchronous_commit = 'on';

-- Simulate real-world naive indexing: index ONLY tenant_id
CREATE INDEX idx_tenant_id_only ON tenant_transactions (tenant_id);

ANALYZE tenant_transactions;
