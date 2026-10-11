#!/usr/bin/env python3
"""
Simulate concurrent webhooks with HMAC signatures and duplicate payloads.
Acceptance validation for Artifact D7 Round 1 sandbox build.
Strict constraint: zero em dashes across all code and text.
"""

import os
import sys
import time
import json
import hmac
import hashlib
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import psycopg2

BASE_URL = os.environ.get("WEBHOOK_BASE_URL", "http://localhost:8088")
SECRET_KEY = os.environ.get("WEBHOOK_SECRET_KEY", "webhook-secret-key-prod-d7-secure-2026")
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = int(os.environ.get("PG_PORT", "5433"))
PG_USER = os.environ.get("PG_USER", "postgres")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "")
PG_DB = os.environ.get("PG_DB", "artifact_d7_db")

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def generate_hmac_signature(secret: str, timestamp: int, payload_str: str) -> str:
    message = f"{timestamp}.{payload_str}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def test_tampered_signature_rejection() -> dict:
    print("[1/3] Testing tampered signature rejection...")
    timestamp = int(time.time())
    payload = {
        "idempotency_key": "evt_tampered_probe_01",
        "amount": 999.99,
        "currency": "USD",
        "customer_id": "cust_attacker"
    }
    raw_body = json.dumps(payload, separators=(',', ':'))
    valid_signature = generate_hmac_signature(SECRET_KEY, timestamp, raw_body)
    # Tamper 1 character in signature
    tampered_sig = ("0" if valid_signature[0] != "0" else "1") + valid_signature[1:]

    headers = {
        "X-Timestamp": str(timestamp),
        "X-Signature": tampered_sig,
        "Content-Type": "application/json"
    }
    t0 = time.perf_counter()
    resp = requests.post(f"{BASE_URL}/api/v1/webhooks/payments", data=raw_body, headers=headers)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert resp.status_code == 401, f"Expected 401 for tampered signature, got {resp.status_code}"
    print(f"  -> Successfully rejected tampered signature with HTTP 401 in {elapsed_ms:.2f}ms")
    return {
        "tampered_signature_status": resp.status_code,
        "rejection_latency_ms": round(elapsed_ms, 3),
        "rejected_correctly": True
    }


def send_single_webhook(item: tuple) -> dict:
    idx, payload_dict, is_duplicate = item
    raw_body = json.dumps(payload_dict, separators=(',', ':'))
    timestamp = int(time.time())
    signature = generate_hmac_signature(SECRET_KEY, timestamp, raw_body)

    headers = {
        "X-Timestamp": str(timestamp),
        "X-Signature": signature,
        "Content-Type": "application/json"
    }

    t0 = time.perf_counter()
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/webhooks/payments", data=raw_body, headers=headers, timeout=10)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        data = resp.json() if resp.status_code == 200 else {}
        return {
            "index": idx,
            "idempotency_key": payload_dict["idempotency_key"],
            "is_duplicate_intended": is_duplicate,
            "status_code": resp.status_code,
            "response_status": data.get("status"),
            "latency_ms": elapsed_ms,
            "success": resp.status_code == 200
        }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "index": idx,
            "idempotency_key": payload_dict["idempotency_key"],
            "is_duplicate_intended": is_duplicate,
            "status_code": 0,
            "response_status": "error",
            "error": str(e),
            "latency_ms": elapsed_ms,
            "success": False
        }


def run_concurrent_workload() -> dict:
    print("[2/3] Firing 500 webhooks (375 unique, 125 duplicates) across 20 concurrent threads...")

    # Reset backend state
    reset_resp = requests.post(f"{BASE_URL}/api/v1/webhooks/reset")
    assert reset_resp.status_code == 200, "Failed to reset webhook database state"

    # Create 375 unique payloads
    unique_payloads = []
    for i in range(1, 376):
        unique_payloads.append({
            "idempotency_key": f"evt_prod_{i:04d}",
            "amount": round(random.uniform(10.0, 500.0), 2),
            "currency": "USD",
            "customer_id": f"cust_{random.randint(100, 999)}",
            "event_type": "payment.succeeded"
        })

    # Pick 125 payloads to duplicate
    # Random sample of 125 from the 375 unique payloads
    dup_sample = random.sample(unique_payloads, 125)

    # Workload items: (index, payload, is_duplicate)
    items = []
    for idx, p in enumerate(unique_payloads):
        items.append((idx, p, False))
    for idx, p in enumerate(dup_sample):
        items.append((len(unique_payloads) + idx, p, True))

    # Shuffle to simulate interleaved and concurrent deliveries
    random.seed(42)
    random.shuffle(items)

    total_requests = len(items)
    assert total_requests == 500, f"Expected 500 requests, got {total_requests}"

    t_start = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_map = {executor.submit(send_single_webhook, item): item for item in items}
        for future in as_completed(future_map):
            results.append(future.result())

    total_time_s = time.perf_counter() - t_start
    throughput_rps = total_requests / total_time_s

    # Analyze outcomes
    processed_count = sum(1 for r in results if r.get("response_status") == "processed")
    already_processed_count = sum(1 for r in results if r.get("response_status") == "already_processed")
    error_count = sum(1 for r in results if not r.get("success"))

    latencies = [r["latency_ms"] for r in results if "latency_ms" in r]
    latencies.sort()

    p50 = latencies[int(len(latencies) * 0.50)]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    avg_latency = sum(latencies) / len(latencies)

    print(f"  -> Total requests completed: {total_requests}")
    print(f"  -> Unique processed: {processed_count} (Expected: 375)")
    print(f"  -> Duplicates detected & handled: {already_processed_count} (Expected: 125)")
    print(f"  -> Errors: {error_count} (Expected: 0)")
    print(f"  -> Throughput: {throughput_rps:.2f} req/s in {total_time_s:.2f}s")
    print(f"  -> Latency: avg={avg_latency:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")

    assert processed_count == 375, f"Expected exactly 375 unique payments processed, got {processed_count}"
    assert already_processed_count == 125, f"Expected exactly 125 duplicate deliveries, got {already_processed_count}"
    assert error_count == 0, f"Expected 0 errors, got {error_count}"

    return {
        "total_webhooks_sent": total_requests,
        "unique_payments_processed": processed_count,
        "duplicate_deliveries_handled": already_processed_count,
        "errors_encountered": error_count,
        "total_duration_seconds": round(total_time_s, 3),
        "throughput_req_per_sec": round(throughput_rps, 2),
        "latency_ms": {
            "mean": round(avg_latency, 2),
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
            "min": round(latencies[0], 2),
            "max": round(latencies[-1], 2)
        }
    }


def verify_database_state() -> dict:
    print("[3/3] Verifying PostgreSQL 18 database integrity on port 5433...")
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DB
    )
    cursor = conn.cursor()

    cursor.execute("SELECT count(*) FROM d7_webhook_sandbox.processed_events;")
    db_events_count = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM d7_webhook_sandbox.payment_ledger;")
    db_ledger_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT idempotency_key, count(*) 
        FROM d7_webhook_sandbox.payment_ledger 
        GROUP BY idempotency_key 
        HAVING count(*) > 1;
    """)
    duplicate_ledger_rows = cursor.fetchall()

    conn.close()

    print(f"  -> Rows in processed_events table: {db_events_count}")
    print(f"  -> Rows in payment_ledger table: {db_ledger_count}")
    print(f"  -> Double credits detected in payment_ledger: {len(duplicate_ledger_rows)}")

    assert db_events_count == 375, f"Expected 375 in processed_events, found {db_events_count}"
    assert db_ledger_count == 375, f"Expected 375 in payment_ledger, found {db_ledger_count}"
    assert len(duplicate_ledger_rows) == 0, f"Double credits detected: {duplicate_ledger_rows}"

    return {
        "db_processed_events_count": db_events_count,
        "db_payment_ledger_count": db_ledger_count,
        "double_credits_detected": len(duplicate_ledger_rows),
        "database_integrity_verified": True
    }


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    tamper_result = test_tampered_signature_rejection()
    workload_result = run_concurrent_workload()
    db_result = verify_database_state()

    metrics = {
        "artifact": "Artifact D7 (Service 20): Idempotent Webhook Ingestion Engine with HMAC",
        "phase": "Round 1: Sandbox Build",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tamper_verification": tamper_result,
        "workload_benchmark": workload_result,
        "database_verification": db_result,
        "acceptance_criteria": {
            "exactly_375_unique_payments_processed": workload_result["unique_payments_processed"] == 375,
            "zero_double_credits": db_result["double_credits_detected"] == 0,
            "all_125_duplicates_handled_with_http_200": workload_result["duplicate_deliveries_handled"] == 125,
            "tampered_signature_rejected_with_http_401": tamper_result["rejected_correctly"],
            "database_tables_in_sync": db_result["db_processed_events_count"] == db_result["db_payment_ledger_count"] == 375
        }
    }

    metrics_path = os.path.join(OUTPUT_DIR, "webhook_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to: {metrics_path}")

    # Generate SHA256SUMS.txt
    manifest_files = [
        "webhook_metrics.json"
    ]

    manifest_path = os.path.join(OUTPUT_DIR, "SHA256SUMS.txt")
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        for fname in manifest_files:
            fpath = os.path.join(OUTPUT_DIR, fname)
            if os.path.exists(fpath):
                checksum = compute_sha256(fpath)
                f.write(f"{checksum}  {fname}\n")
    print(f"Manifest written to: {manifest_path}")

    print("\nALL ROUND 1 ACCEPTANCE CRITERIA SATISFIED WITH 100% SUCCESS.")


if __name__ == "__main__":
    main()
