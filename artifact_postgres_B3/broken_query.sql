-- Find recent user login events ordered by timestamp
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING)
SELECT 
    id, 
    user_id, 
    created_at, 
    metadata->>'ip_address' AS client_ip,
    metadata->>'session_id' AS session_id
FROM audit_events
WHERE metadata->>'action_type' = 'USER_LOGIN'
  AND created_at >= NOW() - INTERVAL '30 days'
ORDER BY created_at DESC
LIMIT 50;
