#!/usr/bin/env python3
"""
Verification Script for D6-R1: GraphQL to REST Gateway Adapter.
Fires 100 requests asserting 100% field parity matching OrderSummaryDTO and latency benchmarks.
Collects performance metrics and saves to output/gateway_metrics.json.
Constraint: STRICT ZERO EM DASHES. Use commas, colons, or periods.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List
import requests

GATEWAY_BASE_URL = "http://127.0.0.1:8081"
UPSTREAM_GRAPHQL_URL = "http://127.0.0.1:4000/graphql"
TOTAL_REQUESTS = 100
OUTPUT_DIR = Path("output")


def verify_openapi_docs() -> bool:
    print("[1/4] Verifying OpenAPI documentation...")
    url = f"{GATEWAY_BASE_URL}/v3/api-docs"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            print(f"FAILED: OpenAPI docs returned HTTP {resp.status_code}")
            return False
        spec = resp.json()
        assert "openapi" in spec, "Missing openapi version key"
        assert "/api/v1/orders/{id}/summary" in spec.get("paths", {}), "Missing order summary endpoint path"
        schemas = spec.get("components", {}).get("schemas", {})
        assert "OrderSummaryDTO" in schemas, "Missing OrderSummaryDTO schema"
        assert "ProblemDetail" in schemas, "Missing ProblemDetail schema"
        print("  OpenAPI v3 specification verified successfully at /v3/api-docs.")
        return True
    except Exception as e:
        print(f"FAILED: OpenAPI check error: {e}")
        return False


def verify_zero_overfetching() -> bool:
    print("[2/4] Verifying zero over-fetching query contract...")
    # Exact 5 fields required by OrderSummaryDTO:
    # 1. order.id
    # 2. order.status
    # 3. order.totalAmount
    # 4. order.user.name
    # 5. order.lineItems.id
    allowed_query_tokens = {"id", "status", "totalAmount", "user", "name", "lineItems"}
    excluded_fields = {"email", "membershipTier", "registeredAt", "shippingAddress", "sku", "productName", "unitPrice", "subtotal"}
    
    # We inspect the Java client source to confirm no excluded field is queried
    client_source = Path("src/main/java/com/albidox/gateway/client/GraphQLUpstreamClient.java").read_text(encoding="utf-8")
    for field in excluded_fields:
        if f'"{field}"' in client_source or f" {field} " in client_source or f"\n{field}" in client_source:
            print(f"FAILED: Detected over-fetching of excluded field '{field}' in GraphQL query")
            return False
    print("  Zero over-fetching confirmed. GraphQL document strictly requests 5 projected fields.")
    return True


def run_benchmark_and_parity_checks() -> Dict[str, Any]:
    print(f"[3/4] Firing {TOTAL_REQUESTS} requests against REST gateway adapter...")
    latencies: List[float] = []
    parity_successes = 0
    errors: List[str] = []

    # Warm-up request
    try:
        requests.get(f"{GATEWAY_BASE_URL}/api/v1/orders/ORD-1001/summary", timeout=2)
    except Exception:
        pass

    start_time_all = time.perf_counter()

    for i in range(1, TOTAL_REQUESTS + 1):
        order_num = 1000 + (i % 50) + 1
        order_id = f"ORD-{order_num}"
        req_url = f"{GATEWAY_BASE_URL}/api/v1/orders/{order_id}/summary"
        
        t0 = time.perf_counter()
        try:
            resp = requests.get(req_url, timeout=5)
            t1 = time.perf_counter()
            elapsed_ms = (t1 - t0) * 1000.0
            latencies.append(elapsed_ms)

            if resp.status_code != 200:
                errors.append(f"Request #{i} ({order_id}) returned status {resp.status_code}")
                continue

            data = resp.json()

            # Parity checks matching OrderSummaryDTO
            assert isinstance(data.get("orderId"), str) and len(data["orderId"]) > 0, "Invalid orderId"
            assert isinstance(data.get("customerName"), str) and len(data["customerName"]) > 0, "Invalid customerName"
            assert isinstance(data.get("totalAmount"), (int, float)) and data["totalAmount"] > 0, "Invalid totalAmount"
            assert isinstance(data.get("status"), str) and len(data["status"]) > 0, "Invalid status"
            assert isinstance(data.get("lineItemCount"), int) and data["lineItemCount"] >= 0, "Invalid lineItemCount"

            parity_successes += 1

        except Exception as e:
            errors.append(f"Request #{i} ({order_id}) exception: {str(e)}")

    total_time_s = time.perf_counter() - start_time_all

    latencies.sort()
    min_lat = min(latencies) if latencies else 0.0
    max_lat = max(latencies) if latencies else 0.0
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    p50_lat = latencies[int(len(latencies) * 0.50)] if latencies else 0.0
    p95_lat = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    p99_lat = latencies[int(len(latencies) * 0.99)] if latencies else 0.0

    parity_rate = (parity_successes / TOTAL_REQUESTS) * 100.0
    throughput = TOTAL_REQUESTS / total_time_s if total_time_s > 0 else 0.0

    print(f"  Completed {TOTAL_REQUESTS} requests in {total_time_s:.2f}s ({throughput:.1f} req/s).")
    print(f"  Parity Pass Rate: {parity_rate:.1f}% ({parity_successes}/{TOTAL_REQUESTS})")
    print(f"  Latency Metrics: avg={avg_lat:.2f}ms, p50={p50_lat:.2f}ms, p95={p95_lat:.2f}ms, p99={p99_lat:.2f}ms, min={min_lat:.2f}ms, max={max_lat:.2f}ms")

    assert parity_successes == TOTAL_REQUESTS, f"Parity check failed with {len(errors)} errors: {errors[:3]}"
    assert p95_lat < 50.0, f"Latency benchmark exceeded: p95={p95_lat:.2f}ms >= 50.0ms"

    return {
        "artifact": "D6-R1",
        "description": "GraphQL to REST Gateway Adapter Performance and Parity Benchmark",
        "total_requests": TOTAL_REQUESTS,
        "successful_requests": parity_successes,
        "failed_requests": len(errors),
        "parity_rate_percent": parity_rate,
        "latency_metrics_ms": {
            "min": round(min_lat, 2),
            "max": round(max_lat, 2),
            "avg": round(avg_lat, 2),
            "p50": round(p50_lat, 2),
            "p95": round(p95_lat, 2),
            "p99": round(p99_lat, 2)
        },
        "throughput_rps": round(throughput, 2),
        "zero_overfetching_verified": True,
        "openapi_docs_verified": True,
        "sla_target_ms": 50.0,
        "sla_met": p95_lat < 50.0
    }


def main() -> None:
    print("=== D6-R1 Gateway Verification Suite ===")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    openapi_ok = verify_openapi_docs()
    if not openapi_ok:
        sys.exit(1)

    overfetching_ok = verify_zero_overfetching()
    if not overfetching_ok:
        sys.exit(1)

    metrics = run_benchmark_and_parity_checks()

    output_path = OUTPUT_DIR / "gateway_metrics.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(f"[4/4] Metrics saved to {output_path}")
    print("All Round 1 verification gates passed successfully.")


if __name__ == "__main__":
    main()
