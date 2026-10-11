#!/usr/bin/env python3
"""
run_tests.py
Automated test runner and metric generation harness for Artifact D10.
Executes JUnit 5 regression test suite against native PostgreSQL 18,
parses Surefire XML reports, generates output/qa_metrics.json,
and generates output/SHA256SUMS.txt.

Constraint: STRICT ZERO EM DASHES. Use commas, colons, or periods.
"""

import os
import sys
import time
import json
import hashlib
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, Any, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SUREFIRE_DIR = os.path.join(BASE_DIR, "target", "surefire-reports")
METRICS_FILE = os.path.join(OUTPUT_DIR, "qa_metrics.json")
SHA256_FILE = os.path.join(OUTPUT_DIR, "SHA256SUMS.txt")


def run_maven_tests() -> float:
    print("=== Executing Maven Integration Test Suite ===")
    start_time = time.perf_counter()
    result = subprocess.run(
        ["mvn.cmd", "test"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        shell=True
    )
    elapsed = time.perf_counter() - start_time
    print(f"Maven test run completed in {elapsed:.2f}s with exit code {result.returncode}.")
    if result.returncode != 0:
        print("ERROR: Maven test run failed.")
        print(result.stdout)
        print(result.stderr)
        sys.exit(result.returncode)
    return elapsed


def parse_surefire_reports() -> Dict[str, Any]:
    print("=== Parsing Surefire XML Reports ===")
    if not os.path.isdir(SUREFIRE_DIR):
        print(f"ERROR: Surefire reports directory not found at {SUREFIRE_DIR}")
        sys.exit(1)

    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0
    suite_elapsed_time = 0.0
    suites: List[Dict[str, Any]] = []
    test_cases: List[Dict[str, Any]] = []

    for filename in sorted(os.listdir(SUREFIRE_DIR)):
        if filename.startswith("TEST-") and filename.endswith(".xml"):
            xml_path = os.path.join(SUREFIRE_DIR, filename)
            tree = ET.parse(xml_path)
            root = tree.getroot()

            s_name = root.attrib.get("name", filename)
            s_tests = int(root.attrib.get("tests", 0))
            s_failures = int(root.attrib.get("failures", 0))
            s_errors = int(root.attrib.get("errors", 0))
            s_skipped = int(root.attrib.get("skipped", 0))
            s_time = float(root.attrib.get("time", 0.0))

            total_tests += s_tests
            total_failures += s_failures
            total_errors += s_errors
            total_skipped += s_skipped
            suite_elapsed_time += s_time

            suite_cases: List[Dict[str, Any]] = []
            for tc in root.findall("testcase"):
                tc_name = tc.attrib.get("name", "unknown")
                tc_classname = tc.attrib.get("classname", s_name)
                tc_time = float(tc.attrib.get("time", 0.0))
                failure_el = tc.find("failure")
                error_el = tc.find("error")
                skipped_el = tc.find("skipped")

                if failure_el is not None:
                    status = "FAILED"
                elif error_el is not None:
                    status = "ERROR"
                elif skipped_el is not None:
                    status = "SKIPPED"
                else:
                    status = "PASSED"

                tc_record = {
                    "name": tc_name,
                    "classname": tc_classname,
                    "duration_seconds": tc_time,
                    "status": status
                }
                suite_cases.append(tc_record)
                test_cases.append(tc_record)

            suites.append({
                "suite_name": s_name,
                "tests": s_tests,
                "failures": s_failures,
                "errors": s_errors,
                "skipped": s_skipped,
                "duration_seconds": s_time,
                "cases": suite_cases
            })

    passed_tests = total_tests - total_failures - total_errors - total_skipped
    pass_rate = (passed_tests / total_tests * 100.0) if total_tests > 0 else 0.0

    return {
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": total_failures,
        "error_tests": total_errors,
        "skipped_tests": total_skipped,
        "pass_rate_percent": pass_rate,
        "surefire_total_time_seconds": round(suite_elapsed_time, 3),
        "suites": suites,
        "test_cases": test_cases
    }


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_manifest():
    print("=== Generating SHA-256 Checksum Manifest ===")
    entries = []
    for item in sorted(os.listdir(OUTPUT_DIR)):
        if item == "SHA256SUMS.txt":
            continue
        item_path = os.path.join(OUTPUT_DIR, item)
        if os.path.isfile(item_path):
            checksum = compute_sha256(item_path)
            entries.append(f"{checksum}  {item}")

    with open(SHA256_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(entries) + "\n")
    print(f"Manifest written to {SHA256_FILE} with {len(entries)} items.")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    execution_time = run_maven_tests()
    report_data = parse_surefire_reports()

    metrics = {
        "artifact_id": "D10",
        "round": "R1",
        "service": "Automated Data Validation and Regression Test Harness",
        "target_database": "PostgreSQL 18.0",
        "port": 5433,
        "schema_isolation": "d10_regression_sandbox",
        "timestamp_epoch": time.time(),
        "wall_clock_time_seconds": round(execution_time, 3),
        "surefire_execution_time_seconds": report_data["surefire_total_time_seconds"],
        "under_20s_sla": report_data["surefire_total_time_seconds"] < 20.0,
        "total_tests": report_data["total_tests"],
        "passed_tests": report_data["passed_tests"],
        "failed_tests": report_data["failed_tests"],
        "error_tests": report_data["error_tests"],
        "skipped_tests": report_data["skipped_tests"],
        "pass_rate_percent": report_data["pass_rate_percent"],
        "suites": report_data["suites"],
        "test_cases": report_data["test_cases"]
    }

    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to {METRICS_FILE}.")

    generate_manifest()
    print("=== Suite Run Completed Successfully ===")


if __name__ == "__main__":
    main()
