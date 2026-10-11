DROP TABLE IF EXISTS audit_events CASCADE;

CREATE TABLE audit_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL
);

-- Seed 1,000,000 rows with varied realistic JSONB audit payloads
-- Disable synchronous commit during bulk generation for speed
SET synchronous_commit = 'off';
SET maintenance_work_mem = '256MB';

INSERT INTO audit_events (user_id, created_at, metadata)
SELECT
    gen_random_uuid(),
    NOW() - (random() * 180 * INTERVAL '1 day'),
    jsonb_build_object(
        'action_type', (ARRAY['USER_LOGIN', 'PAGE_VIEW', 'DATA_EXPORT', 'ADMIN_OVERRIDE', 'LOGOUT', 'PASSWORD_RESET'])[(random() * 5 + 1)::int],
        'ip_address', '192.168.' || (random() * 255)::int || '.' || (random() * 255)::int,
        'user_agent', (ARRAY[
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'
        ])[(random() * 2 + 1)::int],
        'session_id', gen_random_uuid()::text,
        'http_status', (ARRAY[200, 201, 401, 403, 500])[(random() * 4 + 1)::int],
        'latency_ms', (random() * 250 + 5)::int
    )
FROM generate_series(1, 1000000) AS g;

SET synchronous_commit = 'on';

ANALYZE audit_events;
