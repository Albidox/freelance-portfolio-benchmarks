# Dynamic JavaScript / SPA Content Extraction: Proof of Work

## Problem Statement
Modern web applications, single-page applications (SPAs), and dynamic catalogs frequently render their primary data on the client side using JavaScript frameworks (React, Vue, Angular, or jQuery). When clients attempt to scrape these targets using standard HTTP libraries such as `requests`, `urllib`, or plain `BeautifulSoup`, the response contains only empty skeleton HTML shells and placeholder script tags. Business-critical content remains completely unrendered, leading to failed pipelines and zero extracted rows. Extracting this data reliably requires browser automation engines that execute client scripts, wait for asynchronous DOM hydration, and enforce strict data validation contracts.

## The Proof: Why Standard HTTP Fails
To empirically demonstrate this failure mode, `proof_http_fails.py` queries `https://quotes.toscrape.com/js/` using standard `requests.get()` and parses the response with BeautifulSoup. 

The raw HTTP response yields:
- **HTTP Status:** 200 OK
- **Raw Response Size:** 5,806 bytes
- **Quotes Found:** 0 (`div.quote` elements: 0, `span.text` elements: 0)
- **Verdict:** Content is completely absent from the initial HTML payload.

The full audit evidence is preserved in `output/http_failure_proof.txt`.

## The Solution: Browser-Based Dynamic Extraction
The production extraction engine in `scraper.py` implements a resilient three-tier browser runtime hierarchy:
1. **Playwright via Chrome DevTools Protocol (CDP :9222):** Connects directly to an existing browser instance for ultra-fast, authenticated execution with minimal overhead.
2. **Camoufox Standalone (Headless):** Antidetect Firefox-based browser fallback with fingerprint spoofing and stealth defaults.
3. **Playwright Bundled Chromium:** Autonomous headless fallback ensuring deterministic execution in any CI/CD environment.

The pipeline monitors DOM mutation events via `page.wait_for_selector("div.quote", timeout=10000)`, captures the fully hydrated DOM, validates every quote record against strict Pydantic v2 schemas (`QuoteRecord`), and streams clean data into dual production formats: RFC 4180 CSV and compressed Snappy Parquet.

## Hero Metrics (Live Run Verification)
- **Target URL:** `https://quotes.toscrape.com/js/` (Pages 1 to 10)
- **HTTP Extraction Yield:** 0 quotes (0% coverage)
- **Browser Extraction Yield:** 100 quotes across 10 pages (100% coverage)
- **Validation Failures:** 0 records rejected
- **Total Pipeline Execution Time:** 22.07 seconds
- **Browser Backend Connected:** Playwright CDP (:9222)

### Side-by-Side Comparison
| Method | Quotes Found | Execution Mechanism | Root Cause / Behavior |
| :--- | :--- | :--- | :--- |
| `requests.get()` + `BeautifulSoup` | 0 | Raw HTTP GET socket | JavaScript does not execute; only raw skeleton HTML is returned |
| `Playwright` / `Camoufox` Browser | 100 | Full V8 / Gecko JavaScript Engine | Client-side scripts execute and hydrate DOM containers dynamically |

## Output Deliverables
All deliverables are generated inside the `output/` directory:

| File | Format | Description |
| :--- | :--- | :--- |
| `output/http_failure_proof.txt` | Plain Text | Forensic proof confirming HTTP returns zero quotes |
| `output/quotes_dataset.csv` | CSV (RFC 4180) | Clean 100-row tabular dataset with headers (101 lines) |
| `output/quotes_dataset.snappy.parquet` | Apache Parquet | High-performance binary columnar dataset with Snappy compression |
| `output/quotes_js_dataset.csv` | CSV (RFC 4180) | Canonical dataset copy matching execution specification |
| `output/quotes_js_dataset.snappy.parquet` | Apache Parquet | Canonical Parquet copy matching execution specification |
| `output/SHA256SUMS.txt` | Cryptographic Hashes | SHA-256 verification checksums for data integrity validation |
| `output/run_log.txt` | Timestamped Audit Log | Execution log capturing per-page timings and backend provenance |
| `output/real_world_spa_probe_report.md` | Markdown Report | Real-world stress test report across 4 dynamic SPA targets |
| `output/real_world_js_probe_report.md` | Markdown Report | Canonical specification copy of real-world dynamic probe report |

## When to Use Browser Automation vs Plain HTTP
- **Use Plain HTTP / Scrapling:** When the target serves static HTML or server-rendered pages (SSR). This provides maximum throughput (100+ requests/sec) and minimal resource footprint.
- **Use Browser Automation (Playwright / Camoufox):** When the target relies on client-side rendering (React, Angular, Vue, Next.js client hydration), AJAX pagination, dynamic infinite scroll, Shadow DOM components, or aggressive behavioral bot checks.

## How to Run

### 1. Environment Setup
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Run HTTP Failure Proof
```bash
python proof_http_fails.py
```
Output artifact generated at `output/http_failure_proof.txt`.

### 3. Run Production Browser Scraper
```bash
python scraper.py
```
Output datasets and checksums generated in `output/`.

### 4. Run Real-World Dynamic SPA Probes (Round 2)
```bash
python probe_spa_sites.py
```
Outputs live comparison report across GitHub, Quotes Scroll, HN Algolia, and X/Twitter in `output/real_world_spa_probe_report.md`.

### 5. Run Test Verification Suite
```bash
python verify_artifacts.py
```

## Tech Stack
- **Language & Runtime:** Python 3.11
- **Browser Automation:** Playwright (CDP :9222 & Chromium), Camoufox
- **HTML Parsing:** BeautifulSoup4, lxml
- **Data Contracts & Validation:** Pydantic v2
- **Columnar Storage:** PyArrow (Snappy Parquet)
- **HTTP Forensics:** Requests

## Author & Attribution
- **Engineer:** Sk Ashfaq Bux
- **GitHub:** [https://github.com/Albidox](https://github.com/Albidox)
- **Portfolio Deliverable:** Artifact A3 (Dynamic JavaScript / SPA Content Extraction)
