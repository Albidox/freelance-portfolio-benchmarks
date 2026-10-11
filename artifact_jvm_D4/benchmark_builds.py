#!/usr/bin/env python3
"""
Automated benchmark and verification suite for Artifact D4.
Compares unoptimized baseline monolithic build against multi-stage modular build.
Measures disk footprint, asserts sub-100MB target (>85% reduction), tests HTTP health check,
generates SHA-256 checksum manifest, and verifies strict zero em dash compliance.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request


def compute_directory_size(path: str) -> int:
    """Recursively computes total size in bytes of all files in a directory."""
    total_bytes = 0
    for root, _, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            if not os.path.islink(fp) and os.path.exists(fp):
                total_bytes += os.path.getsize(fp)
    return total_bytes


def sha256_file(path: str) -> str:
    """Computes SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def check_zero_em_dashes(base_dir: str) -> list[str]:
    """Scans text files for disallowed em dashes."""
    violations = []
    extensions = (".py", ".baseline", ".optimized", ".xml", ".yml", ".yaml", ".md", ".txt", ".java", ".sh", ".bat")
    for root, _, files in os.walk(base_dir):
        if ".git" in root or ".venv" in root or "target" in root or "dist" in root:
            continue
        for f in files:
            if f.endswith(extensions) or "Dockerfile" in f:
                fp = os.path.join(root, f)
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                        for line_no, line in enumerate(fh, 1):
                            if "\u2014" in line:
                                violations.append(f"{fp}:{line_no} contains em dash (\\u2014)")
                            if "\u2013" in line:
                                violations.append(f"{fp}:{line_no} contains en dash (\\u2013)")
                except Exception as err:
                    violations.append(f"{fp}: Read error: {err}")
    return violations


def get_bash_executable() -> str:
    """Finds the proper Git Bash executable avoiding Microsoft WSL stub."""
    git_bash = r"C:\Program Files\Git\bin\bash.exe"
    if os.path.exists(git_bash):
        return git_bash
    return "bash"


def run_benchmark():
    script_dir = os.path.abspath(os.path.dirname(__file__))
    os.chdir(script_dir)
    bash_exe = get_bash_executable()

    print("=" * 76)
    print("ARTIFACT D4: JVM OPTIMIZATION & LAYERED RUNTIME BENCHMARK")
    print("=" * 76)

    # 1. Execute baseline build script
    print("\n[1/6] Executing baseline build script...")
    t0 = time.perf_counter()
    res_baseline = subprocess.run([bash_exe, "build_script.baseline"], capture_output=True, text=True)
    if res_baseline.returncode != 0:
        print("[ERROR] Baseline build failed:")
        print("STDOUT:", res_baseline.stdout)
        print("STDERR:", res_baseline.stderr)
        sys.exit(1)
    baseline_build_sec = time.perf_counter() - t0
    print(f"      Baseline build finished in {baseline_build_sec:.2f}s")

    # 2. Execute optimized build script
    print("\n[2/6] Executing optimized build script...")
    t0 = time.perf_counter()
    res_optimized = subprocess.run([bash_exe, "build_script.optimized"], capture_output=True, text=True)
    if res_optimized.returncode != 0:
        print("[ERROR] Optimized build failed:")
        print(res_optimized.stderr)
        sys.exit(1)
    optimized_build_sec = time.perf_counter() - t0
    print(f"      Optimized build finished in {optimized_build_sec:.2f}s")

    # 3. Measure directory footprints
    print("\n[3/6] Measuring deployment directory footprints...")
    dist_baseline = os.path.join(script_dir, "dist", "baseline")
    dist_optimized = os.path.join(script_dir, "dist", "optimized")
    dist_runtime = os.path.join(dist_optimized, "runtime")
    dist_app = os.path.join(dist_optimized, "app")
    dist_layers = os.path.join(script_dir, "dist", "layers")

    baseline_bytes = compute_directory_size(dist_baseline)
    optimized_bytes = compute_directory_size(dist_optimized)
    runtime_bytes = compute_directory_size(dist_runtime)
    app_bytes = compute_directory_size(dist_app)

    baseline_mb = baseline_bytes / (1024 * 1024)
    optimized_mb = optimized_bytes / (1024 * 1024)
    runtime_mb = runtime_bytes / (1024 * 1024)
    app_mb = app_bytes / (1024 * 1024)

    reduction_pct = ((baseline_bytes - optimized_bytes) / baseline_bytes) * 100.0

    print(f"      Baseline Monolithic Footprint: {baseline_mb:.2f} MB ({baseline_bytes:,} bytes)")
    print(f"      Optimized Modular Footprint:   {optimized_mb:.2f} MB ({optimized_bytes:,} bytes)")
    print(f"        -> Custom JRE (jlink):       {runtime_mb:.2f} MB ({runtime_bytes:,} bytes)")
    print(f"        -> Extracted App Layers:     {app_mb:.2f} MB ({app_bytes:,} bytes)")
    print(f"      Net Footprint Reduction:       {reduction_pct:.2f}%")

    # Layer breakdown if available
    layers_summary = {}
    if os.path.exists(dist_layers):
        for layer_name in os.listdir(dist_layers):
            layer_path = os.path.join(dist_layers, layer_name)
            if os.path.isdir(layer_path):
                l_bytes = compute_directory_size(layer_path)
                layers_summary[layer_name] = {
                    "bytes": l_bytes,
                    "mb": round(l_bytes / (1024 * 1024), 2)
                }
                print(f"           * Layer [{layer_name}]: {l_bytes / (1024 * 1024):.2f} MB")

    # 4. Verify Round 1 Acceptance Assertions
    print("\n[4/6] Verifying Round 1 sizing assertions...")
    assert_size_passed = optimized_mb < 100.0
    assert_reduction_passed = reduction_pct > 85.0

    print(f"      [ASSERT 1] Optimized size < 100MB:     {'PASS' if assert_size_passed else 'FAIL'} ({optimized_mb:.2f} MB)")
    print(f"      [ASSERT 2] Size reduction > 85%:       {'PASS' if assert_reduction_passed else 'FAIL'} ({reduction_pct:.2f}%)")

    if not assert_size_passed or not assert_reduction_passed:
        print("[ERROR] Sizing criteria failed!")
        sys.exit(1)

    # 5. Service Startup and Health Verification
    print("\n[5/6] Verifying service runtime startup and health endpoint...")
    test_port = 8098
    java_exe = os.path.join(dist_runtime, "bin", "java.exe")
    if not os.path.exists(java_exe):
        java_exe = os.path.join(dist_runtime, "bin", "java")

    app_dir = dist_app
    server_proc = subprocess.Popen(
        [
            java_exe,
            f"-Dserver.port={test_port}",
            "org.springframework.boot.loader.launch.JarLauncher"
        ],
        cwd=app_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    health_url = f"http://127.0.0.1:{test_port}/actuator/health"
    status_url = f"http://127.0.0.1:{test_port}/api/v1/status"
    health_passed = False
    startup_time_ms = None
    health_payload = {}
    status_payload = {}

    start_probe = time.perf_counter()
    timeout_sec = 25.0
    while time.perf_counter() - start_probe < timeout_sec:
        if server_proc.poll() is not None:
            stdout, stderr = server_proc.communicate()
            print("[ERROR] Service terminated unexpectedly during startup:")
            print(stderr or stdout)
            sys.exit(1)
        try:
            with urllib.request.urlopen(health_url, timeout=1.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("status") == "UP":
                        startup_time_ms = int((time.perf_counter() - start_probe) * 1000)
                        health_passed = True
                        health_payload = data
                        break
        except Exception:
            time.sleep(0.3)

    if health_passed:
        try:
            with urllib.request.urlopen(status_url, timeout=1.0) as resp:
                if resp.status == 200:
                    status_payload = json.loads(resp.read().decode("utf-8"))
        except Exception as err:
            print(f"[WARN] Failed to query status endpoint: {err}")

    # Terminate service cleanly
    server_proc.terminate()
    try:
        server_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server_proc.kill()

    print(f"      [ASSERT 3] GET /actuator/health status UP: {'PASS' if health_passed else 'FAIL'} (Latency: {startup_time_ms}ms)")
    if status_payload:
        print(f"      Service Status: {status_payload.get('status')} | Heap Used: {status_payload.get('heap_used_mb')}MB")

    if not health_passed:
        print("[ERROR] Service health check verification failed!")
        sys.exit(1)

    # 6. Checksum Manifest and Zero Em Dash Audit
    print("\n[6/6] Generating SHA-256 checksum manifest and auditing punctuation...")
    output_dir = os.path.join(script_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    # Build metrics record
    metrics = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseline_size_bytes": baseline_bytes,
        "baseline_size_mb": round(baseline_mb, 2),
        "optimized_size_bytes": optimized_bytes,
        "optimized_size_mb": round(optimized_mb, 2),
        "runtime_size_mb": round(runtime_mb, 2),
        "app_size_mb": round(app_mb, 2),
        "reduction_percentage": round(reduction_pct, 2),
        "layers": layers_summary,
        "health_check": {
            "endpoint": "/actuator/health",
            "status": health_payload.get("status"),
            "startup_latency_ms": startup_time_ms,
            "heap_used_mb": status_payload.get("heap_used_mb")
        },
        "assertions": {
            "optimized_under_100mb": assert_size_passed,
            "reduction_exceeds_85pct": assert_reduction_passed,
            "health_up": health_passed
        }
    }

    metrics_file = os.path.join(output_dir, "build_metrics.json")
    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    # Key files for SHA256 manifest
    manifest_targets = [
        "pom.xml",
        "build_script.baseline",
        "build_script.optimized",
        "benchmark_builds.py",
        "Dockerfile.baseline",
        "Dockerfile.optimized",
        os.path.join("target", "artifact-jvm-d4-1.0.0.jar"),
        os.path.join("output", "build_metrics.json"),
        os.path.join("dist", "optimized", "runtime", "lib", "modules")
    ]

    sha256_entries = []
    for rel_path in manifest_targets:
        full_path = os.path.join(script_dir, rel_path)
        if os.path.exists(full_path):
            digest = sha256_file(full_path)
            norm_path = rel_path.replace("\\", "/")
            sha256_entries.append(f"{digest}  {norm_path}")

    sums_file = os.path.join(output_dir, "SHA256SUMS.txt")
    with open(sums_file, "w", encoding="utf-8") as f:
        f.write("\n".join(sha256_entries) + "\n")

    print(f"      Generated {len(sha256_entries)} SHA-256 checksums in output/SHA256SUMS.txt")

    # Zero em dash audit
    violations = check_zero_em_dashes(script_dir)
    print(f"      [ASSERT 4] Zero em dash audit:         {'PASS' if not violations else 'FAIL'} ({len(violations)} violations)")
    if violations:
        for v in violations:
            print(f"        Violation: {v}")
        sys.exit(1)

    print("\n" + "=" * 76)
    print("ALL ROUND 1 ACCEPTANCE CRITERIA VERIFIED AND PASSED!")
    print("=" * 76)


if __name__ == "__main__":
    run_benchmark()
