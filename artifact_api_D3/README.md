# REST API Mock Server & Postman Collection Generator (Artifact D3)

Enterprise-grade automated tooling that converts OpenAPI 3.0 specifications into Postman Collections v2.1 with embedded assertion scripts, simulates realistic backend latency and RFC 7807 problem details via a FastAPI mock server, and verifies contracts using Newman CLI.

## Key Features

1. **OpenAPI 3.0 Compliant:** Complete multi-endpoint schema for authentication, catalog querying, cart management, and order checkout flows.
2. **Postman Collection v2.1 Generation:** Deterministic conversion with pre-request authentication hooks and 25 automated assertions.
3. **Realistic Mock Server:** FastAPI-based mock engine featuring realistic payload generation, RFC 7807 problem details error handling, and 50ms to 120ms simulated network latency.
4. **Newman Verification Suite:** Headless collection execution with detailed metrics reporting, JSON exports, and zero test failures.
5. **Epistemic Audit & Integrity:** Complete SHA-256 checksum manifest generated for all deliverables.

## Directory Structure

```
artifact_api_D3/
├── openapi_spec.yaml              # OpenAPI 3.0 specification
├── generate_postman_collection.py # YAML to Postman Collection v2.1 compiler
├── mock_server.py                 # FastAPI realistic mock server with latency
├── verify_collection.py           # Newman test runner and acceptance verifier
├── run_stress_probes.py           # Real-world stress probe and contract drift runner
├── requirements.txt               # Python package dependencies
├── package.json                   # Node.js dev dependencies (Newman)
└── output/
    ├── collection.json            # Generated Postman Collection v2.1
    ├── environment.json           # Postman environment variables
    ├── newman_report.json         # Automated Newman run execution report
    ├── contract_drift_probe_report.md # Round 2 stress probe report and benchmarks
    └── SHA256SUMS.txt             # Cryptographic checksum manifest
```

## Setup and Verification

### 1. Initialize Virtual Environment
```bash
uv venv --python 3.11 .venv
.venv/Scripts/python -m pip install -r requirements.txt
npm install newman --save-dev
```

### 2. Generate Postman Collection
```bash
.venv/Scripts/python generate_postman_collection.py
```

### 3. Run Automated Newman Verification
```bash
.venv/Scripts/python verify_collection.py
```

### 4. Run Real-World Stress Probes (Round 2)
```bash
.venv/Scripts/python run_stress_probes.py
```

## Round 1 Acceptance Results

- **Test Pass Rate:** 100% across all 25 assertions (25 passed, 0 failed).
- **Generation Speed:** 0.041 seconds (target threshold < 2.50 seconds).
- **Contract Coverage:** 5 endpoints (Auth, Products List, Product Detail, Cart Items, Order Checkout).
- **Average Response Latency:** 111ms (simulated network latency 50ms to 120ms).
- **Artifact Manifest:** Full SHA-256 manifest produced in `output/SHA256SUMS.txt`.

## Round 2 Real-World Stress Probe Results

- **Contract Drift Detection:** 100% trapped; Newman test suite flagged precise schema mutations (omitted fields, type mismatches) with non-zero exit code.
- **High-Concurrency Load:** 500 requests completed across 50 worker threads with 100% HTTP 200 success rate and > 700 req/s throughput.
- **Memory Stability:** Zero memory growth (initial 4.02 MB, peak 4.02 MB, final 4.02 MB).
- **Invalid Auth Handling:** 6/6 test cases verified for strict RFC 7807 Problem Details conformance across HTTP 401 and HTTP 403 status codes.
- **Punctuation Standard:** Zero em dashes across all code comments, manifests, and reports.
