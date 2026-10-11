#!/usr/bin/env python3
"""
Benchmark Caching: Spring Boot 3.4 In-Memory / Valkey Caching Layer
Measures cold vs warm latency, cache hit ratios, and eviction correctness.
Constraint: Strict zero em dashes in comments, docstrings, and outputs.
"""

import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import requests

BASE_URL = "http://127.0.0.1:8085"
TARGET_JAR = Path("target/artifact-caching-d5-1.0.0.jar").resolve()
OUTPUT_DIR = Path("output").resolve()
METRICS_FILE = OUTPUT_DIR / "caching_metrics.json"
CHECKSUM_FILE = OUTPUT_DIR / "SHA256SUMS.txt"


def wait_for_server(timeout_sec=60):
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            r = requests.get(f"{BASE_URL}/actuator/health", timeout=1.0)
            if r.status_code == 200 and r.json().get("status") == "UP":
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def start_server_if_needed():
    try:
        r = requests.get(f"{BASE_URL}/actuator/health", timeout=1.0)
        if r.status_code == 200 and r.json().get("status") == "UP":
            print("Server already running on port 8085.")
            return None
    except Exception:
        pass

    if not TARGET_JAR.exists():
        raise FileNotFoundError(f"Target jar not found at {TARGET_JAR}. Run mvn package first.")

    print(f"Starting Spring Boot application: {TARGET_JAR}")
    proc = subprocess.Popen(
        ["java", "-jar", str(TARGET_JAR)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    if not wait_for_server(60):
        proc.terminate()
        raise RuntimeError("Spring Boot application failed to start within 60 seconds.")
    print("Spring Boot application started successfully.")
    return proc


def compute_percentiles(latencies_ms):
    if not latencies_ms:
        return {"p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "mean_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0}
    sorted_lats = sorted(latencies_ms)
    n = len(sorted_lats)

    def percentile(p):
        idx = int(p * n)
        if idx >= n:
            idx = n - 1
        return sorted_lats[idx]

    return {
        "p50_ms": round(percentile(0.50), 3),
        "p95_ms": round(percentile(0.95), 3),
        "p99_ms": round(percentile(0.99), 3),
        "mean_ms": round(sum(sorted_lats) / n, 3),
        "min_ms": round(sorted_lats[0], 3),
        "max_ms": round(sorted_lats[-1], 3),
        "total_requests": n
    }


def execute_request(session, sku):
    t0 = time.perf_counter()
    resp = session.get(f"{BASE_URL}/api/v1/products/{sku}", timeout=10.0)
    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000.0
    if resp.status_code != 200:
        raise RuntimeError(f"Unexpected status code {resp.status_code} for SKU {sku}: {resp.text}")
    return latency_ms


def run_benchmark():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    server_process = start_server_if_needed()

    try:
        # Clear cache and reset query counters
        r_clear = requests.post(f"{BASE_URL}/api/v1/products/cache/clear", timeout=5.0)
        assert r_clear.status_code == 200, "Failed to clear cache"
        print("Cache cleared. Resetting query counters.")

        # Ensure DB latency is configured to 150ms
        requests.post(f"{BASE_URL}/api/v1/products/simulation/latency?ms=150", timeout=5.0)

        # Cold phase: Request 50 distinct products for the first time
        cold_skus = [f"PROD-{i:05d}" for i in range(1, 51)]
        print(f"Running Cold Phase across {len(cold_skus)} distinct items...")

        cold_latencies = []
        cold_session = requests.Session()
        for sku in cold_skus:
            lat = execute_request(cold_session, sku)
            cold_latencies.append(lat)

        cold_stats = compute_percentiles(cold_latencies)
        print(f"Cold Phase Results: p50={cold_stats['p50_ms']}ms, p95={cold_stats['p95_ms']}ms, p99={cold_stats['p99_ms']}ms")

        # Get cache stats after cold phase
        stats_after_cold = requests.get(f"{BASE_URL}/api/v1/products/cache/stats", timeout=5.0).json()
        print(f"Stats after cold phase: {json.dumps(stats_after_cold)}")

        # Warm phase: 10,000 requests against the already cached SKUs using connection pooling
        total_warm_requests = 10000
        concurrency = 2
        warm_sku_pool = cold_skus
        print(f"Running Warm Phase: {total_warm_requests} requests across {concurrency} persistent workers...")

        warm_latencies = []

        def worker(requests_per_worker):
            s = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
            s.mount("http://", adapter)
            lats = []
            for i in range(requests_per_worker):
                sku = warm_sku_pool[i % len(warm_sku_pool)]
                lat = execute_request(s, sku)
                lats.append(lat)
            return lats

        reqs_per_worker = total_warm_requests // concurrency
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(worker, reqs_per_worker) for _ in range(concurrency)]
            for fut in concurrent.futures.as_completed(futures):
                warm_latencies.extend(fut.result())

        warm_stats = compute_percentiles(warm_latencies)
        print(f"Warm Phase Results: p50={warm_stats['p50_ms']}ms, p95={warm_stats['p95_ms']}ms, p99={warm_stats['p99_ms']}ms")

        # Get final cache metrics
        final_cache_info = requests.get(f"{BASE_URL}/api/v1/products/cache/stats", timeout=5.0).json()
        cache_metrics = final_cache_info.get("metrics", {})
        hit_ratio_percent = cache_metrics.get("hitRatioPercent", 0.0)
        print(f"Final Cache Metrics: {json.dumps(cache_metrics)}")
        print(f"Hit Ratio: {hit_ratio_percent}%")

        # Eviction test verification
        test_sku = "PROD-00042"
        orig_prod = requests.get(f"{BASE_URL}/api/v1/products/{test_sku}", timeout=5.0).json()
        print(f"Original product {test_sku} price: {orig_prod['price']}")

        update_payload = {
            "name": "High Performance Quantum Cloud Module",
            "description": "Updated enterprise compute block for eviction validation",
            "category": "Compute",
            "price": 888.88,
            "stockQuantity": 99
        }
        r_put = requests.put(f"{BASE_URL}/api/v1/products/{test_sku}", json=update_payload, timeout=5.0)
        assert r_put.status_code == 200, f"Update failed: {r_put.text}"
        updated_prod = r_put.json()
        assert float(updated_prod["price"]) == 888.88, "Updated price mismatch in PUT response"

        # Read immediately: verify fresh data served
        fresh_read = requests.get(f"{BASE_URL}/api/v1/products/{test_sku}", timeout=5.0).json()
        assert float(fresh_read["price"]) == 888.88, "Eviction verification failed: stale data returned"
        assert fresh_read["name"] == update_payload["name"], "Updated name mismatch in fresh read"
        print(f"Eviction verified successfully: Fresh price {fresh_read['price']} served immediately.")

        speedup_factor = round(cold_stats["p50_ms"] / warm_stats["p50_ms"], 2) if warm_stats["p50_ms"] > 0 else 0.0
        print(f"Speedup Factor (p50): {speedup_factor}x")

        # Compile final metrics
        metrics_output = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "artifact_id": "D5",
            "round": "R1",
            "service": "Redis / Valkey Caching Layer Integration",
            "cold_metrics": cold_stats,
            "warm_metrics": warm_stats,
            "speedup_factor": speedup_factor,
            "cache_metrics": cache_metrics,
            "database_query_count": final_cache_info.get("dbQueryCount"),
            "eviction_verification": {
                "sku": test_sku,
                "verified": True,
                "updated_price": 888.88,
                "fresh_read_verified": True
            },
            "gate_criteria_eval": {
                "sub_5ms_warm_p50": warm_stats["p50_ms"] < 5.0,
                "speedup_exceeds_40x": speedup_factor >= 40.0,
                "hit_ratio_exceeds_99": hit_ratio_percent >= 99.0,
                "eviction_verified": True
            }
        }

        with open(METRICS_FILE, "w", encoding="utf-8") as f:
            json.dump(metrics_output, f, indent=2)
        print(f"Metrics written to {METRICS_FILE}")

        # Generate SHA256 checksum manifest
        generate_checksums()

        # Assert gate criteria
        assert warm_stats["p50_ms"] < 5.0, f"Warm p50 {warm_stats['p50_ms']}ms is not under 5.0ms"
        assert speedup_factor >= 40.0, f"Speedup factor {speedup_factor}x is below 40.0x"
        assert hit_ratio_percent >= 99.0, f"Hit ratio {hit_ratio_percent}% is below 99.0%"
        print("ALL ROUND 1 GATE CRITERIA PASSED.")

    finally:
        if server_process is not None:
            print("Stopping background Spring Boot process...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()


def generate_checksums():
    files_to_hash = [
        Path("output/caching_metrics.json"),
        Path("schema_setup.sql"),
        Path("src/main/java/com/albidox/caching/config/CacheConfig.java"),
        Path("src/main/java/com/albidox/caching/service/ProductService.java"),
        Path("src/main/java/com/albidox/caching/controller/ProductController.java"),
        Path("src/main/java/com/albidox/caching/dto/ProductDto.java"),
        Path("src/main/java/com/albidox/caching/entity/Product.java"),
        Path("pom.xml")
    ]

    lines = []
    for fp in files_to_hash:
        p = Path(fp)
        if p.exists():
            h = hashlib.sha256()
            with open(p, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            # Use relative POSIX path for portability
            rel_path = p.as_posix()
            lines.append(f"{h.hexdigest()}  {rel_path}")

    with open(CHECKSUM_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Checksum manifest written to {CHECKSUM_FILE}")


if __name__ == "__main__":
    run_benchmark()
