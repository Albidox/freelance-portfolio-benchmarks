"""
Browser-based scraper for JavaScript-rendered quotes (quotes.toscrape.com/js/).
Extracts quotes across all 10 paginated pages, validates via Pydantic v2 QuoteRecord,
and exports to CSV, Snappy Parquet, SHA256 checksums, and execution logs.
"""
import csv
import datetime
import hashlib
import os
import sys
import time
from typing import List, Tuple

from bs4 import BeautifulSoup
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import ValidationError

from schema import QuoteRecord


def compute_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class BrowserManager:
    """Manages browser connection lifecycle across CDP, Camoufox, and Chromium fallbacks."""

    def __init__(self):
        self.backend = None
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.is_cdp = False

    def start(self):
        # 1. Attempt Playwright CDP :9222
        try:
            from playwright.sync_api import sync_playwright
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=5000)
            self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
            self.page = self.context.new_page()
            self.backend = "Playwright CDP (:9222)"
            self.is_cdp = True
            print(f"[Browser] Successfully connected via {self.backend}")
            return self
        except Exception as exc_cdp:
            print(f"[Browser] CDP connection failed: {exc_cdp}. Falling back to Camoufox standalone...")

        # 2. Attempt Camoufox standalone
        try:
            from camoufox.sync_api import Camoufox
            self.browser = Camoufox(headless=True).__enter__()
            self.page = self.browser.new_page()
            self.backend = "Camoufox Standalone (Headless)"
            self.is_cdp = False
            print(f"[Browser] Successfully connected via {self.backend}")
            return self
        except Exception as exc_camoufox:
            print(f"[Browser] Camoufox fallback failed: {exc_camoufox}. Falling back to Playwright Chromium...")

        # 3. Attempt Playwright bundled Chromium
        try:
            if not self.playwright:
                from playwright.sync_api import sync_playwright
                self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
            self.context = self.browser.new_context()
            self.page = self.context.new_page()
            self.backend = "Playwright Bundled Chromium"
            self.is_cdp = False
            print(f"[Browser] Successfully launched {self.backend}")
            return self
        except Exception as exc_pw:
            print(f"[Browser] Chromium launch failed: {exc_pw}")
            if self.playwright:
                self.playwright.stop()
            raise RuntimeError("All browser automation backends failed.") from exc_pw

    def close(self):
        try:
            if self.page:
                self.page.close()
        except Exception:
            pass

        if not self.is_cdp and self.browser:
            try:
                self.browser.close()
            except Exception:
                pass

        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass


def scrape_quotes() -> Tuple[List[QuoteRecord], int, str, float]:
    """Execute scraping run across all 10 pages."""
    start_time = time.time()
    manager = BrowserManager()
    manager.start()

    log_entries = []
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log_entries.append(f"[{timestamp}] Scraper run initiated. Backend: {manager.backend}")

    valid_records: List[QuoteRecord] = []
    validation_failures = 0

    try:
        for page_num in range(1, 11):
            page_start = time.time()
            url = f"https://quotes.toscrape.com/js/page/{page_num}/"
            print(f"[Scraper] Fetching Page {page_num}/10: {url} ...")

            manager.page.goto(url, timeout=20000)
            try:
                manager.page.wait_for_selector("div.quote", timeout=10000)
            except Exception as e:
                err_msg = f"Page {page_num}: Timeout waiting for div.quote: {e}"
                print(f"[Scraper] {err_msg}")
                log_entries.append(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] {err_msg}")
                break

            html_content = manager.page.content()
            soup = BeautifulSoup(html_content, "html.parser")
            quote_divs = soup.select("div.quote")

            page_extracted = 0
            for q_div in quote_divs:
                text_el = q_div.select_one("span.text")
                author_el = q_div.select_one("small.author") or q_div.select_one(".author")
                author_link_el = q_div.select_one("a[href*='/author/']") or q_div.select_one("span a")
                tag_els = q_div.select("div.tags a.tag") or q_div.select(".tag")

                raw_text = text_el.get_text(strip=True) if text_el else ""
                raw_author = author_el.get_text(strip=True) if author_el else ""
                raw_author_url = author_link_el.get("href", "").strip() if author_link_el else ""
                raw_tags = [t.get_text(strip=True) for t in tag_els]

                try:
                    record = QuoteRecord(
                        text=raw_text,
                        author=raw_author,
                        author_url=raw_author_url,
                        tags=raw_tags,
                        page_number=page_num,
                    )
                    valid_records.append(record)
                    page_extracted += 1
                except ValidationError as ve:
                    validation_failures += 1
                    val_err = f"Page {page_num} validation failure: {ve}"
                    print(f"[Validation Error] {val_err}")
                    log_entries.append(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] {val_err}")

            page_elapsed = time.time() - page_start
            entry = f"Page {page_num:02d}: Extracted {page_extracted} quotes (valid={len(valid_records)}, failures={validation_failures}) in {page_elapsed:.2f}s"
            print(f"[Scraper] {entry}")
            log_entries.append(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] {entry}")

            # Polite delay between pages
            if page_num < 10:
                time.sleep(1.5)

    finally:
        manager.close()

    elapsed = time.time() - start_time
    summary_line = (
        f"Extraction complete in {elapsed:.2f}s. "
        f"Backend: {manager.backend}. Total pages: 10. "
        f"Total valid quotes: {len(valid_records)}. Validation failures: {validation_failures}."
    )
    print(f"\n[Summary] {summary_line}")
    log_entries.append(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] {summary_line}")

    # Ensure output directory exists
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # 1. Export CSV
    csv_filenames = ["quotes_dataset.csv", "quotes_js_dataset.csv"]
    for csv_name in csv_filenames:
        csv_path = os.path.join(output_dir, csv_name)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["text", "author", "author_url", "tags", "page_number"])
            for r in valid_records:
                tags_joined = ", ".join(r.tags)
                writer.writerow([r.text, r.author, r.author_url, tags_joined, r.page_number])

    # 2. Export Snappy Parquet
    parquet_filenames = ["quotes_dataset.snappy.parquet", "quotes_js_dataset.snappy.parquet"]
    parquet_data = [
        {
            "text": r.text,
            "author": r.author,
            "author_url": r.author_url,
            "tags": r.tags,
            "page_number": r.page_number,
        }
        for r in valid_records
    ]
    arrow_table = pa.Table.from_pylist(parquet_data)
    for pq_name in parquet_filenames:
        pq_path = os.path.join(output_dir, pq_name)
        pq.write_table(arrow_table, pq_path, compression="snappy")

    # 3. Compute SHA256 hashes
    checksum_lines = []
    all_artifacts = csv_filenames + parquet_filenames + ["http_failure_proof.txt"]
    for filename in sorted(all_artifacts):
        target_path = os.path.join(output_dir, filename)
        if os.path.exists(target_path):
            sha_val = compute_sha256(target_path)
            checksum_lines.append(f"{sha_val}  {filename}")

    sha_file = os.path.join(output_dir, "SHA256SUMS.txt")
    with open(sha_file, "w", encoding="utf-8") as f:
        f.write("\n".join(checksum_lines) + "\n")

    # 4. Write run log
    log_file = os.path.join(output_dir, "run_log.txt")
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("\n".join(log_entries) + "\n")

    return valid_records, validation_failures, manager.backend, elapsed


if __name__ == "__main__":
    records, failures, backend, duration = scrape_quotes()
