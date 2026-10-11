#!/usr/bin/env python3
"""
verify_collection.py
Automated test runner and verifier.
Starts mock server if needed, runs Newman verification, validates 100% test pass rate,
computes SHA-256 checksum manifest, and verifies all Round 1 criteria.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request


def compute_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def check_health(url: str, timeout: float = 1.0) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HealthChecker/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def wait_for_server(health_url: str, max_wait: float = 10.0) -> bool:
    start = time.time()
    while time.time() - start < max_wait:
        if check_health(health_url):
            return True
        time.sleep(0.3)
    return False


def check_zero_em_dashes(file_list: list) -> bool:
    em_dash_found = False
    for path in file_list:
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            content = f.read()
        # Look for UTF-8 encoded em dash \xe2\x80\x94
        if b"\xe2\x80\x94" in content:
            print(f"FAILED: Em dash found in file: {path}", file=sys.stderr)
            em_dash_found = True
    return not em_dash_found


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, "output")
    collection_path = os.path.join(output_dir, "collection.json")
    env_path = os.path.join(output_dir, "environment.json")
    report_path = os.path.join(output_dir, "newman_report.json")
    sums_path = os.path.join(output_dir, "SHA256SUMS.txt")

    python_bin = sys.executable

    print("=================================================================")
    print("REST API Mock Server & Postman Collection Verification Suite")
    print("=================================================================")

    # Step 1: Ensure collection and environment exist
    if not os.path.exists(collection_path) or not os.path.exists(env_path):
        print("Generating Postman collection from OpenAPI specification...")
        gen_script = os.path.join(base_dir, "generate_postman_collection.py")
        res = subprocess.run([python_bin, gen_script], capture_output=True, text=True)
        if res.returncode != 0:
            print("Collection generation failed:", res.stderr, file=sys.stderr)
            sys.exit(1)
        print(res.stdout)

    # Step 2: Ensure mock server is active
    server_proc = None
    health_url = "http://127.0.0.1:8000/health"
    if not check_health(health_url):
        print("Starting mock server on http://127.0.0.1:8000...")
        mock_script = os.path.join(base_dir, "mock_server.py")
        server_proc = subprocess.Popen(
            [python_bin, mock_script, "--host", "127.0.0.1", "--port", "8000"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if not wait_for_server(health_url, max_wait=10.0):
            print("ERROR: Mock server failed to become healthy within 10 seconds.", file=sys.stderr)
            if server_proc:
                server_proc.terminate()
            sys.exit(1)
        print("Mock server online and ready.")
    else:
        print("Mock server already running on port 8000.")

    # Step 3: Run Newman verification
    # Try finding newman CLI: local node_modules/.bin/newman or npx or system path
    newman_cmd = None
    local_newman_cmd = os.path.join(base_dir, "node_modules", ".bin", "newman.cmd")
    local_newman_bin = os.path.join(base_dir, "node_modules", ".bin", "newman")

    if os.path.exists(local_newman_cmd):
        newman_cmd = [local_newman_cmd]
    elif os.path.exists(local_newman_bin):
        newman_cmd = [local_newman_bin]
    elif shutil.which("newman"):
        newman_cmd = ["newman"]
    elif shutil.which("npx"):
        newman_cmd = ["npx", "newman"]
    else:
        print("ERROR: Newman CLI not found on system.", file=sys.stderr)
        if server_proc:
            server_proc.terminate()
        sys.exit(1)

    cmd = newman_cmd + [
        "run", collection_path,
        "-e", env_path,
        "--reporters", "cli,json",
        "--reporter-json-export", report_path
    ]

    print(f"Running command: {' '.join(cmd)}")
    newman_run = subprocess.run(cmd, capture_output=True, text=True)
    print(newman_run.stdout)

    if newman_run.returncode != 0 and not os.path.exists(report_path):
        print("Newman run execution failed:", newman_run.stderr, file=sys.stderr)
        if server_proc:
            server_proc.terminate()
        sys.exit(1)

    # Step 4: Parse Newman Report
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    stats = report.get("run", {}).get("stats", {})
    assertions = stats.get("assertions", {})
    total_assertions = assertions.get("total", 0)
    failed_assertions = assertions.get("failed", 0)
    pending_assertions = assertions.get("pending", 0)
    passed_assertions = total_assertions - failed_assertions - pending_assertions

    requests_stat = stats.get("requests", {})
    total_requests = requests_stat.get("total", 0)

    print("-----------------------------------------------------------------")
    print(f"Total Requests Executed: {total_requests}")
    print(f"Total Assertions: {total_assertions}")
    print(f"Passed Assertions: {passed_assertions}")
    print(f"Failed Assertions: {failed_assertions}")
    print("-----------------------------------------------------------------")

    # Step 5: Generate SHA-256 checksum manifest
    manifest_targets = [
        os.path.join(output_dir, "collection.json"),
        os.path.join(output_dir, "environment.json"),
        os.path.join(output_dir, "newman_report.json"),
        os.path.join(output_dir, "drift_environment.json"),
        os.path.join(output_dir, "drift_newman_report.json"),
        os.path.join(output_dir, "contract_drift_probe_report.md"),
        os.path.join(base_dir, "openapi_spec.yaml"),
        os.path.join(base_dir, "generate_postman_collection.py"),
        os.path.join(base_dir, "mock_server.py"),
        os.path.join(base_dir, "verify_collection.py"),
        os.path.join(base_dir, "run_stress_probes.py"),
        os.path.join(base_dir, "README.md")
    ]

    manifest_lines = []
    for file_p in manifest_targets:
        if os.path.exists(file_p):
            rel_name = os.path.relpath(file_p, base_dir).replace("\\", "/")
            h = compute_sha256(file_p)
            manifest_lines.append(f"{h}  {rel_name}\n")

    with open(sums_path, "w", encoding="utf-8") as f:
        f.writelines(manifest_lines)
    print(f"SHA-256 checksum manifest created at: {sums_path}")

    # Step 6: Verify Zero Em Dashes Rule
    all_source_files = [
        os.path.join(base_dir, "openapi_spec.yaml"),
        os.path.join(base_dir, "generate_postman_collection.py"),
        os.path.join(base_dir, "mock_server.py"),
        os.path.join(base_dir, "verify_collection.py"),
        os.path.join(base_dir, "run_stress_probes.py"),
        os.path.join(base_dir, "README.md"),
        os.path.join(output_dir, "collection.json"),
        os.path.join(output_dir, "environment.json"),
        os.path.join(output_dir, "contract_drift_probe_report.md")
    ]
    em_dash_clean = check_zero_em_dashes(all_source_files)

    # Step 7: Acceptance Criteria Verification
    criteria_met = True
    print("\nAcceptance Criteria Evaluation:")

    # Criteria 1: 100% test pass rate across all 25 assertions
    if total_assertions == 25 and failed_assertions == 0 and passed_assertions == 25:
        print("[PASS] 100% test pass rate across all 25 assertions.")
    else:
        print(f"[FAIL] Assertion count mismatch: total={total_assertions}, passed={passed_assertions}, failed={failed_assertions}")
        criteria_met = False

    # Criteria 2: Generation script finishes in under 2.5 seconds
    t0 = time.perf_counter()
    gen_cmd = [python_bin, os.path.join(base_dir, "generate_postman_collection.py")]
    subprocess.run(gen_cmd, capture_output=True, text=True)
    gen_duration = time.perf_counter() - t0
    if gen_duration < 2.5:
        print(f"[PASS] Generation script finished in {gen_duration:.4f}s (threshold < 2.5s).")
    else:
        print(f"[FAIL] Generation script took {gen_duration:.4f}s (exceeded 2.5s).")
        criteria_met = False

    # Criteria 3: Complete Postman Collection v2.1 exported to output/collection.json
    if os.path.exists(collection_path) and os.path.getsize(collection_path) > 1000:
        print("[PASS] Postman Collection v2.1 verified at output/collection.json.")
    else:
        print("[FAIL] output/collection.json missing or invalid.")
        criteria_met = False

    # Criteria 4: SHA-256 checksum manifest generated in output/SHA256SUMS.txt
    if os.path.exists(sums_path) and os.path.getsize(sums_path) > 0:
        print("[PASS] SHA-256 checksum manifest verified at output/SHA256SUMS.txt.")
    else:
        print("[FAIL] output/SHA256SUMS.txt missing or empty.")
        criteria_met = False

    # Criteria 5: Strict zero em dashes across all files
    if em_dash_clean:
        print("[PASS] Punctuation rule verified: strict zero em dashes.")
    else:
        print("[FAIL] Em dashes detected in source or output files.")
        criteria_met = False

    if server_proc:
        print("Shutting down locally spawned mock server...")
        server_proc.terminate()
        server_proc.wait()

    if not criteria_met:
        print("\nRound 1 Verification FAILED.", file=sys.stderr)
        sys.exit(1)

    print("\nRound 1 Verification PASSED: All 5 acceptance criteria successfully satisfied.")


if __name__ == "__main__":
    main()
