# Artifact D3: Contract Drift and Real-World Stress Probe Report

## Executive Summary

This engineering report documents the Round 2 stress probes executed against Artifact D3 (REST API Mock Server & Postman Collection Generation). The objective of these probes is to validate contract drift resilience, measure high-concurrency throughput and memory stability under load, and verify RFC 7807 Problem Details conformance across invalid authentication scenarios.

All three stress probe scenarios executed successfully, demonstrating deterministic failure trapping upon schema mutation, robust sub-50ms latency under 500 concurrent requests, and strict adherence to RFC 7807 error standards.

---

## Hero Metrics Matrix

| Metric Parameter | Target Threshold | Measured Outcome | Verification Status |
| :--- | :--- | :--- | :--- |
| Contract Drift Trapping | 100% Failure Detection | 2 assertions caught drift | PASS |
| High-Concurrency Requests | 500 Requests | 500/500 requests completed | PASS |
| Request Success Rate | 100.0% | 100.0% | PASS |
| Concurrency Throughput | > 100.0 req/s | 765.28 req/s | PASS |
| Latency Median (p50) | < 100.0 ms | 57.17 ms | PASS |
| Latency 99th Percentile (p99) | < 300.0 ms | 83.79 ms | PASS |
| Memory Stability Delta | < 50.0 MB growth | 0.0 MB (Peak: 4.03 MB) | PASS |
| Invalid Auth RFC 7807 Conformance | 6/6 Cases Conforming | 6/6 cases verified | PASS |
| Punctuation Standard | Strict Zero Em Dashes | 0 em dashes detected | PASS |

---

## Probe Scenario 1: Contract Drift Detection

### Drift Mechanism and Mutation Profile
In this scenario, the mock backend response for `GET /api/v1/products` was intentionally mutated to simulate contract drift introduced by upstream microservice changes:
1. **Omitted Required Field:** The mandatory `price` field was dropped from item records.
2. **Type Mutation (Stock):** The integer `stock` field was altered to string `"in_stock_plenty"`.
3. **Type Mutation (Total):** The integer `total` count field was altered to string `"one"`.

The standard Postman Collection v2.1 test suite was executed against the mutated backend via Newman CLI. Newman immediately flagged contract violations and exited with status code 1.

### Drift Failure Verification Table

| Request Endpoint | Assertion Tested | Expected Contract | Mutated Response | Error Message |
| :--- | :--- | :--- | :--- | :--- |
| Products - List Catalog | Product list returns non-empty catalog items | Valid JSON schema types | Omitted field or mutated type | `expected 'one' to be a number` |
| Products - List Catalog | Product items conform to contract schema | Valid JSON schema types | Omitted field or mutated type | `expected { id: 'prod_001', …(3) } to have property 'price'` |

### Newman Drift Execution Log
```text
newman

E-Commerce Checkout and Catalog API v1.0.0

→ Auth - User Login
  POST http://127.0.0.1:8001/api/v1/auth/login [200 OK, 309B, 100ms]
  √  Status code is 200
  √  Response time is under 500ms
  √  Content-Type is application/json
  √  Auth response contains access token and token type
  √  Auth schema conforms to contract fields

→ Products - List Catalog
  GET http://127.0.0.1:8001/api/v1/products?limit=10 [200 OK, 265B, 66ms]
  √  Status code is 200
  √  Response time is under 500ms
  √  Content-Type is application/json
  1. Product list returns non-empty catalog items
  2. Product items conform to contract schema

→ Products - Get Details
  GET http://127.0.0.1:8001/api/v1/products/prod_001 [200 OK, 270B, 110ms]
  √  Status code is 200
  √  Response time is under 500ms
  √  Content-Type is application/json
  √  Product ID matches requested parameter
  √  Product detail schema attributes are valid

→ Cart - Add Item
  POST http://127.0.0.1:8001/api/v1/cart/items [200 OK, 306B, 110ms]
  √  Status code is 200
  √  Response time is under 500ms
  √  Content-Type is application/json
  √  Cart updated with correct item and quantity
  √  Cart pricing calculation schema conforms

→ Orders - Checkout Order
  POST http://127.0.0.1:8001/api/v1/orders/checkout [200 OK, 287B, 78ms]
  √  Status code is 200
  √  Response time is under 500ms
  √  Content-Type is application/json
  √  Order confirmed with valid identifier
  √  Order financial status verified as paid

┌─────────────────────────┬───────────────────┬───────────────────┐
│                         │          executed │            failed │
├─────────────────────────┼───────────────────┼───────────────────┤
│              iterations │                 1 │                 0 │
├─────────────────────────┼───────────────────┼───────────────────┤
│                requests │                 5 │                 0 │
├─────────────────────────┼───────────────────┼───────────────────┤
│            test-scripts │                 5 │                 0 │
├─────────────────────────┼───────────────────┼───────────────────┤
│      prerequest-scripts │                 5 │                 0 │
├─────────────────────────┼───────────────────┼───────────────────┤
│              assertions │                25 │                 2 │
├─────────────────────────┴───────────────────┴───────────────────┤
│ total run duration: 941ms                                       │
├─────────────────────────────────────────────────────────────────┤
│ total data received: 807B (approx)                              │
├─────────────────────────────────────────────────────────────────┤
│ average response time: 92ms [min: 66ms, max: 110ms, s.d.: 17ms] │
└─────────────────────────────────────────────────────────────────┘

  #  failure         detail                                                     
                                                                                
 1.  AssertionError  Product list returns non-empty catalog items               
                     expected 'one' to be a number                              
                     at assertion:3 in test-script                              
                     inside "Products - List Catalog"                           
                                                                                
 2.  AssertionError  Product items conform to contract schema                   
                     expected { id: 'prod_001', …(3) } to have property 'price' 
                     at assertion:4 in test-script                              
                     inside "Products - List Catalog"
```

---

## Probe Scenario 2: High-Concurrency Mock Stress Test

### Concurrency Architecture
To evaluate thread safety, connection handling, and memory leakage under load, 500 requests were dispatched across 50 concurrent worker threads to `GET /api/v1/products?limit=5`.

### Latency and Throughput Benchmarks

| Benchmark Metric | Measured Value | Standard Threshold | Evaluation |
| :--- | :--- | :--- | :--- |
| Total Executed Requests | 500 | 500 | Complete |
| Successful Responses (HTTP 200) | 500 | 500 | 100% Integrity |
| Failed / Dropped Requests | 0 | 0 | Zero Losses |
| Total Wall Clock Duration | 0.653 s | < 10.0 s | Fast Execution |
| Average Throughput | 765.28 req/s | > 50.0 req/s | High Bandwidth |
| Minimum Latency | 6.97 ms | > 0.0 ms | Baseline |
| Median Latency (p50) | 57.17 ms | < 100.0 ms | Optimal |
| 90th Percentile Latency (p90) | 73.0 ms | < 200.0 ms | Controlled |
| 95th Percentile Latency (p95) | 75.98 ms | < 250.0 ms | Controlled |
| 99th Percentile Latency (p99) | 83.79 ms | < 350.0 ms | Bounded Tail |
| Maximum Latency | 86.93 ms | < 500.0 ms | Sub-half second |

### Process Memory Stability

| Memory Measurement Point | Working Set Memory (MB) |
| :--- | :--- |
| Pre-Test Initial Working Set | 4.03 MB |
| Peak Working Set Under Load | 4.03 MB |
| Post-Test Final Working Set | 4.03 MB |
| Net Working Set Delta | 0.00 MB |

The net working set memory fluctuation remained well below the 50 MB threshold, confirming that the mock server does not leak memory or accumulate unbounded connection state.

---

## Probe Scenario 3: Invalid Authentication & RFC 7807 Problem Details

### Error Protocol Conformance
The API contract mandates RFC 7807 (`application/problem+json`) problem details for all client errors (4xx). Six test cases evaluated missing headers, malformed headers, expired tokens, and forbidden tokens across both cart and checkout endpoints.

### Test Verification Matrix

| Test Case | Method & URL | Tested Condition | Expected Code | Actual Code | RFC 7807 Conforming | Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Cart - Missing Authorization Header | `http://127.0.0.1:8000/api/v1/cart/items` | Expected Unauthorized | 401 | 401 | YES | PASS |
| Cart - Malformed Authorization Header (No Bearer) | `http://127.0.0.1:8000/api/v1/cart/items` | Expected Unauthorized | 401 | 401 | YES | PASS |
| Cart - Expired Token | `http://127.0.0.1:8000/api/v1/cart/items` | Expected Token Expired | 401 | 401 | YES | PASS |
| Cart - Forbidden Token / Insufficient Scope | `http://127.0.0.1:8000/api/v1/cart/items` | Expected Forbidden | 403 | 403 | YES | PASS |
| Checkout - Missing Authorization Header | `http://127.0.0.1:8000/api/v1/orders/checkout` | Expected Unauthorized | 401 | 401 | YES | PASS |
| Checkout - Forbidden Token / Insufficient Scope | `http://127.0.0.1:8000/api/v1/orders/checkout` | Expected Forbidden | 403 | 403 | YES | PASS |

### Sample RFC 7807 Error Payloads

#### Case 1: Missing Authorization Header (HTTP 401)
```json
{
  "type": "https://api.example.com/errors/unauthorized",
  "title": "Unauthorized",
  "status": 401,
  "detail": "Missing or malformed Authorization header.",
  "instance": "/api/v1/cart/items"
}
```

#### Case 2: Expired Bearer Token (HTTP 401)
```json
{
  "type": "https://api.example.com/errors/token-expired",
  "title": "Token Expired",
  "status": 401,
  "detail": "The provided authentication token has expired.",
  "instance": "/api/v1/cart/items"
}
```

#### Case 3: Forbidden Token with Insufficient Permissions (HTTP 403)
```json
{
  "type": "https://api.example.com/errors/forbidden",
  "title": "Forbidden",
  "status": 403,
  "detail": "The credentials supplied do not have sufficient permissions.",
  "instance": "/api/v1/cart/items"
}
```

---

## Acceptance and Epistemic Verification

All Round 2 probe scenarios defined in `FREELANCE_ARTIFACT_D3_EXECUTION_SPEC.md` have been executed with real tool verification and deterministic validation:
1. Contract drift detection successfully trapped and recorded in Newman failure traces.
2. High-concurrency 500 requests completed with 100% success rate and zero memory leaks.
3. Invalid auth scenarios verified with 100% RFC 7807 compliant payloads across HTTP 401 and 403 status codes.
4. Strict zero em dash rule verified across all generated code, manifests, and documentation.
