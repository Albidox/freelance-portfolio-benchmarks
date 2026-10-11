-- Aggregates monthly revenue buckets for a specific tenant ordered by date
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING)
SELECT 
    tenant_id,
    DATE_TRUNC('day', created_at) AS day_bucket,
    SUM(amount_cents) AS total_revenue_cents,
    COUNT(*) AS transaction_count
FROM tenant_transactions
WHERE tenant_id = 'a1b2c3d4-0000-0000-0000-000000000001'
  AND created_at >= NOW() - INTERVAL '90 days'
GROUP BY 1, 2
ORDER BY 2 DESC;
