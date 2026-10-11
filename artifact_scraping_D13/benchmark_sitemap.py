"""Benchmark and verification harness for sitemap scraping pipeline.

Spawns MockSitemapServer, executes SitemapScraper against 10 nested gzipped sitemaps
(25,000 URLs), verifies URL parity between CSV and Parquet artifacts, ensures
strict performance envelopes (< 10.0s elapsed, < 45.0MB RAM), and writes
output/sitemap_metrics.json and output/SHA256SUMS.txt.
"""

import asyncio
import csv
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from typing import Dict, List, Optional, Set
import urllib.request

import pyarrow.parquet as pq

from mock_sitemap_server import find_free_port
from sitemap_scraper import SitemapScraper, OUTPUT_DIR, CSV_FILENAME, PARQUET_FILENAME, METRICS_FILENAME

logger = logging.getLogger("benchmark_sitemap")

MAX_RUNTIME_SECONDS = 10.0
MAX_PEAK_MEMORY_MB = 45.0
EXPECTED_TOTAL_URLS = 25000
SHA256_MANIFEST = "SHA256SUMS.txt"


def compute_sha256(filepath: str) -> str:
    """Compute standard SHA-256 hex digest for given file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_sha256_manifest(directory: str, manifest_filename: str = SHA256_MANIFEST) -> str:
    """Generate SHA256SUMS.txt for all files in output directory excluding manifest itself."""
    manifest_path = os.path.join(directory, manifest_filename)
    records: List[str] = []

    filenames = sorted(os.listdir(directory))
    for fname in filenames:
        if fname == manifest_filename:
            continue
        full_path = os.path.join(directory, fname)
        if os.path.isfile(full_path):
            digest = compute_sha256(full_path)
            records.append(f"{digest}  {fname}")

    manifest_content = "\n".join(records) + "\n"
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(manifest_content)

    return manifest_path


async def run_benchmark(host: str = "127.0.0.1", port: Optional[int] = None):
    """Execute full benchmark cycle with assertions."""
    print("=" * 72)
    print("Starting D13-R1 Sitemap Scraper Sandbox Benchmark")
    print(f"Target: 10 Sub-Sitemaps, {EXPECTED_TOTAL_URLS:,} URLs in Nested Gzip Archives")
    print("=" * 72)

    actual_port = port if port is not None else find_free_port(18080)
    server_cmd = [sys.executable, "mock_sitemap_server.py", "--host", host, "--port", str(actual_port)]
    server_proc = subprocess.Popen(
        server_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for mock server healthcheck
    health_url = f"http://{host}:{actual_port}/health"
    index_url = f"http://{host}:{actual_port}/sitemap_index.xml"
    ready = False
    for _ in range(50):
        try:
            with urllib.request.urlopen(health_url, timeout=0.5) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            await asyncio.sleep(0.1)

    if not ready:
        server_proc.terminate()
        server_proc.wait()
        raise RuntimeError(f"Mock sitemap server failed to become healthy at {health_url}")

    try:
        # 2. Run scraper
        start_wall = time.perf_counter()
        scraper = SitemapScraper(
            index_url=index_url,
            output_dir=OUTPUT_DIR,
            concurrency=2,
        )
        result = await scraper.run()
        total_benchmark_time = time.perf_counter() - start_wall

        # 3. Verify output files existence
        csv_path = os.path.join(OUTPUT_DIR, CSV_FILENAME)
        parquet_path = os.path.join(OUTPUT_DIR, PARQUET_FILENAME)
        metrics_path = os.path.join(OUTPUT_DIR, METRICS_FILENAME)

        assert os.path.exists(csv_path), f"Missing CSV output at {csv_path}"
        assert os.path.exists(parquet_path), f"Missing Parquet output at {parquet_path}"
        assert os.path.exists(metrics_path), f"Missing Metrics output at {metrics_path}"

        # 4. Verify CSV contents
        csv_urls: Set[str] = set()
        csv_rows = 0
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                csv_rows += 1
                csv_urls.add(row["loc"])

        # 5. Verify Parquet contents
        parquet_table = pq.read_table(parquet_path)
        parquet_rows = parquet_table.num_rows
        parquet_urls: Set[str] = set(parquet_table["loc"].to_pylist())

        # 6. Parity assertions
        print(f"Validation:")
        print(f"  CSV Row Count: {csv_rows:,}")
        print(f"  Parquet Row Count: {parquet_rows:,}")
        print(f"  Unique URLs in CSV: {len(csv_urls):,}")
        print(f"  Unique URLs in Parquet: {len(parquet_urls):,}")

        assert csv_rows == EXPECTED_TOTAL_URLS, (
            f"CSV row count mismatch. Expected {EXPECTED_TOTAL_URLS}, got {csv_rows}"
        )
        assert parquet_rows == EXPECTED_TOTAL_URLS, (
            f"Parquet row count mismatch. Expected {EXPECTED_TOTAL_URLS}, got {parquet_rows}"
        )
        assert len(csv_urls) == EXPECTED_TOTAL_URLS, (
            f"Duplicate URLs found in CSV. Unique count is {len(csv_urls)}"
        )
        assert csv_urls == parquet_urls, "Discrepancy detected between CSV and Parquet URL sets"

        # 7. Performance envelope assertions
        print(f"\nPerformance Metrics:")
        print(f"  Scraper Execution Time: {result.elapsed_seconds:.3f} s (Threshold: < {MAX_RUNTIME_SECONDS} s)")
        print(f"  Total Benchmark Time: {total_benchmark_time:.3f} s")
        print(f"  Throughput: {result.throughput_urls_per_second:,.1f} URLs/sec")
        print(f"  Peak RAM RSS: {result.peak_memory_mb:.2f} MB (Threshold: < {MAX_PEAK_MEMORY_MB} MB)")

        assert result.elapsed_seconds < MAX_RUNTIME_SECONDS, (
            f"Execution time {result.elapsed_seconds:.3f}s exceeded threshold {MAX_RUNTIME_SECONDS}s"
        )
        assert result.peak_memory_mb < MAX_PEAK_MEMORY_MB, (
            f"Peak memory {result.peak_memory_mb:.2f}MB exceeded threshold {MAX_PEAK_MEMORY_MB}MB"
        )

        # 8. Generate SHA-256 Manifest
        manifest_path = generate_sha256_manifest(OUTPUT_DIR)
        print(f"\nArtifact Checksums generated in {manifest_path}:")
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                print("  " + line.strip())

        print("\nAll D13-R1 acceptance criteria strictly satisfied.")
        print("=" * 72)

    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            server_proc.kill()


def main():
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(run_benchmark())


if __name__ == "__main__":
    main()
