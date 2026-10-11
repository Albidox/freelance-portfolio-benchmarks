"""Production web scraper for books.toscrape.com.

Extracts 1,000 books across 50 paginated catalogue pages, validates each
record against Pydantic v2 data contract, and exports dual-format datasets
(CSV and Snappy Parquet) with SHA-256 cryptographic manifests.
"""
import csv
import hashlib
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sys
import time
from typing import List, Tuple

from bs4 import BeautifulSoup
from pydantic import ValidationError
import pyarrow as pa
import pyarrow.parquet as pq

from schema import BookRecord

try:
    from scrapling import Fetcher
    FETCH_BACKEND = "scrapling"
except ImportError:
    import requests
    FETCH_BACKEND = "requests"

BASE_URL = "https://books.toscrape.com/catalogue/page-{page}.html"
TOTAL_PAGES = 50
POLITE_DELAY_SECONDS = 1.0
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def fetch_html(url: str) -> Tuple[int, str]:
    """Fetch raw HTML from target URL with backend fallback."""
    if FETCH_BACKEND == "scrapling":
        try:
            response = Fetcher.get(url, timeout=30)
            return response.status, response.html_content
        except Exception as exc:
            print(f"Warning: Scrapling fetch error on {url} ({exc}); falling back to requests", file=sys.stderr)
            import requests
            resp = requests.get(url, timeout=30)
            return resp.status_code, resp.text
    else:
        import requests
        resp = requests.get(url, timeout=30)
        return resp.status_code, resp.text


def parse_page(html_content: str, page_num: int) -> Tuple[List[BookRecord], int]:
    """Parse products on a catalogue page and validate with BookRecord."""
    soup = BeautifulSoup(html_content, "html.parser")
    articles = soup.select("article.product_pod")
    valid_records: List[BookRecord] = []
    validation_failures = 0

    for article in articles:
        a_tag = article.select_one("h3 a")
        title = a_tag.get("title") if a_tag and a_tag.has_attr("title") else ""
        if not title and a_tag:
            title = a_tag.get_text(strip=True)
        href = a_tag.get("href", "") if a_tag else ""

        price_el = article.select_one("p.price_color")
        price_text = price_el.get_text(strip=True) if price_el else ""
        clean_price = re.sub(r"[^\d.]", "", price_text)
        try:
            price_val = float(clean_price) if clean_price else -1.0
        except ValueError:
            price_val = -1.0

        rating_el = article.select_one("p.star-rating")
        rating_val = ""
        if rating_el and "class" in rating_el.attrs:
            classes = rating_el["class"]
            rating_candidates = [c for c in classes if c.lower() != "star-rating"]
            if rating_candidates:
                rating_val = rating_candidates[0]

        stock_el = article.select_one("p.instock.availability")
        stock_text = stock_el.get_text(strip=True) if stock_el else ""
        in_stock = "in stock" in stock_text.lower()

        raw_record = {
            "title": title,
            "price_gbp": price_val,
            "rating": rating_val,
            "in_stock": in_stock,
            "detail_url": href,
            "page_number": page_num,
        }

        try:
            validated = BookRecord(**raw_record)
            valid_records.append(validated)
        except ValidationError as err:
            validation_failures += 1
            print(f"Validation error on page {page_num} for '{title}': {err}", file=sys.stderr)

    return valid_records, validation_failures


def export_csv(records: List[BookRecord], dest_path: Path) -> None:
    """Export records to CSV with exact headers and LF newlines."""
    fieldnames = ["title", "price_gbp", "rating", "in_stock", "detail_url", "page_number"]
    with open(dest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for r in records:
            writer.writerow(r.model_dump())


def export_parquet(records: List[BookRecord], dest_path: Path) -> None:
    """Export records to Snappy-compressed Parquet via PyArrow."""
    schema = pa.schema([
        ("title", pa.string()),
        ("price_gbp", pa.float64()),
        ("rating", pa.int64()),
        ("in_stock", pa.bool_()),
        ("detail_url", pa.string()),
        ("page_number", pa.int64()),
    ])
    pylist = [r.model_dump() for r in records]
    table = pa.Table.from_pylist(pylist, schema=schema)
    pq.write_table(table, dest_path, compression="snappy")


def compute_sha256(file_path: Path) -> str:
    """Compute hex SHA-256 digest of a given file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def run_pipeline() -> dict:
    """Execute end-to-end extraction, validation, and export pipeline."""
    start_time = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_log_path = OUTPUT_DIR / "run_log.txt"

    all_records: List[BookRecord] = []
    total_failures = 0
    pages_fetched = 0
    log_lines: List[str] = []

    init_msg = (
        f"[{datetime.now(timezone.utc).isoformat()}] Starting scraping pipeline: "
        f"backend={FETCH_BACKEND}, target={TOTAL_PAGES} pages."
    )
    print(init_msg)
    log_lines.append(init_msg)

    for page_num in range(1, TOTAL_PAGES + 1):
        url = BASE_URL.format(page=page_num)
        status, html = fetch_html(url)
        timestamp = datetime.now(timezone.utc).isoformat()

        if status != 200:
            error_line = f"[{timestamp}] Page {page_num}/{TOTAL_PAGES}: HTTP {status} (ERROR: failed fetch)"
            print(error_line, file=sys.stderr)
            log_lines.append(error_line)
            continue

        pages_fetched += 1
        page_records, page_failures = parse_page(html, page_num)
        total_failures += page_failures
        all_records.extend(page_records)

        log_entry = (
            f"[{timestamp}] Page {page_num:02d}/{TOTAL_PAGES}: HTTP 200 - "
            f"Extracted {len(page_records)} records, {page_failures} validation failures."
        )
        print(log_entry)
        log_lines.append(log_entry)

        if page_num < TOTAL_PAGES:
            time.sleep(POLITE_DELAY_SECONDS)

    elapsed_time = time.time() - start_time

    # Exports
    csv_path = OUTPUT_DIR / "books_dataset.csv"
    parquet_path = OUTPUT_DIR / "books_dataset.snappy.parquet"
    sha_path = OUTPUT_DIR / "SHA256SUMS.txt"

    export_csv(all_records, csv_path)
    export_parquet(all_records, parquet_path)

    csv_sha = compute_sha256(csv_path)
    parquet_sha = compute_sha256(parquet_path)

    sha_content = f"{csv_sha}  books_dataset.csv\n{parquet_sha}  books_dataset.snappy.parquet\n"
    with open(sha_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(sha_content)

    summary_msg = (
        f"[{datetime.now(timezone.utc).isoformat()}] Pipeline complete in {elapsed_time:.2f}s: "
        f"Pages={pages_fetched}/{TOTAL_PAGES}, Records={len(all_records)}, "
        f"Failures={total_failures}, CSV={csv_path.stat().st_size} bytes, "
        f"Parquet={parquet_path.stat().st_size} bytes."
    )
    print(summary_msg)
    log_lines.append(summary_msg)

    with open(run_log_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(log_lines) + "\n")

    return {
        "pages_fetched": pages_fetched,
        "total_records": len(all_records),
        "total_failures": total_failures,
        "elapsed_seconds": round(elapsed_time, 2),
        "csv_path": str(csv_path),
        "csv_size_bytes": csv_path.stat().st_size,
        "csv_sha256": csv_sha,
        "parquet_path": str(parquet_path),
        "parquet_size_bytes": parquet_path.stat().st_size,
        "parquet_sha256": parquet_sha,
        "backend": FETCH_BACKEND,
    }


if __name__ == "__main__":
    stats = run_pipeline()
    print("\n--- Pipeline Run Summary ---")
    print(f"Backend Used:        {stats['backend']}")
    print(f"Pages Fetched:       {stats['pages_fetched']}/{TOTAL_PAGES}")
    print(f"Records Extracted:   {stats['total_records']}")
    print(f"Validation Failures: {stats['total_failures']}")
    print(f"Elapsed Time:        {stats['elapsed_seconds']}s")
    print(f"CSV Size:            {stats['csv_size_bytes']} bytes")
    print(f"Parquet Size:        {stats['parquet_size_bytes']} bytes")
    print(f"CSV SHA256:          {stats['csv_sha256']}")
    print(f"Parquet SHA256:      {stats['parquet_sha256']}")
