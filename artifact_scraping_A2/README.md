# Structured Table & Directory Data Extraction : Proof of Work

## Problem Statement

Businesses and market research teams frequently require structured records trapped inside paginated HTML tables and web directories: government regulatory filings, corporate registries, financial statements, and athletic databases. Naive copy-pasting or ad-hoc browser scrapers introduce high overhead, unvalidated schema drifts, and malformed tabular deliverables. Clients need high-throughput, resilient extraction pipelines that parse multi-column tables, validate field contracts against strict domain models, and deliver executive-grade spreadsheets alongside analytics-ready data files.

## Solution

This production-grade scraper targets paginated tabular directory structures with zero browser footprint (<15MB RAM) using HTTP/2 protocol fetching. It features:
- **Dynamic DOM Discovery:** Auto-detects table markup, semantic CSS selectors (`td.name`, `td.year`, `td.pct`, etc.), and pagination parameters.
- **Bounded Pagination:** Discovers total page count from live navigation controls and walks the pages deterministically without infinite loop risks.
- **Pydantic v2 Data Contract:** Strictly enforces and coerces numeric constraints, ranges, and optional nullable values (e.g. overtime losses, signed goal differentials, floating-point win percentages).
- **Executive Deliverables:** Generates three export formats simultaneously: UTF-8 CSV, Snappy-compressed columnar Parquet, and an executive-styled Excel workbook (`.xlsx`) featuring frozen headers, auto-filters, zebra striping, and auto-fit column widths.
- **Auditable Integrity:** Computes SHA-256 cryptographic hashes for all deliverable files and maintains an execution run log.

## Hero Metrics (Verified Actual Run)

- **Target URL:** `https://www.scrapethissite.com/pages/forms/`
- **Total Pages Scraped:** 24 / 24 pages
- **Total Records Extracted:** 582 hockey team records
- **Data Contract Violations:** 0 validation failures (100% clean data)
- **Extraction Protocol:** Scrapling HTTP/2 Fetcher (zero headless browser RAM overhead)
- **Pipeline Runtime:** 52.79 seconds (including polite 1.0s delay between page requests)
- **Delivered Formats:** CSV, Snappy Parquet, Styled Excel (.xlsx), SHA256SUMS

## How to Run

Ensure Python 3.11+ is installed.

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Execute the extraction pipeline
python scraper.py

# 3. Execute the real-world table probe
python probe_tables.py
```

All deliverable files, execution logs, and probe reports are generated directly in the `output/` directory.

## Real-World Stress Test (Round 2)

The extraction pipeline was stress-tested against 4 real-world public web targets to evaluate table parsing resilience across messy HTML, legacy government schemas, and commercial WAFs:
- **Wikipedia Population Table:** 50 records extracted (100% clean). Handled footnote superscripts (`<sup class="reference">`) and hidden sort spans without array misalignment.
- **SEC EDGAR Company Filings:** 11 live 10-K filings extracted from legacy government HTML tables without semantic classes using custom User-Agent compliance.
- **Yelp Business Directory:** Accurately classified as WAF-protected (DataDome 403 / CAPTCHA on both HTTP/2 and headless browser CDP :9222 fallback). Honest capability boundary documented.
- **Yahoo Finance Financials:** 25 active stock records extracted in 0.8s from server-rendered dynamic tables.

Comprehensive audit details and client scoping guidelines are recorded in `output/real_world_table_probe_report.md`.

## Deliverable Files

| File Path | Format | Description |
|-----------|--------|-------------|
| `output/teams_dataset.csv` | CSV (UTF-8) | Clean tabular raw data export with standardized headers. |
| `output/teams_dataset.snappy.parquet` | Apache Parquet | High-performance, Snappy-compressed columnar format for data warehouse ingestion. |
| `output/teams_dataset.xlsx` | Excel Workbook | Executive deliverable formatted with dark header (`#1E293B`), frozen panes (`A2`), auto-filters, alternating zebra striping (`#F8FAFC`), and column width auto-fit. |
| `output/hockey_teams.*` | CSV / Parquet / Excel | Convenience alias artifacts ensuring 100% specification compatibility. |
| `output/SHA256SUMS.txt` | Text / Hashes | Cryptographic SHA-256 verification hashes for all generated files. |
| `output/run_log.txt` | Text / Log | Timestamped execution log tracing pagination walk and row extraction counts. |

## Key Differentiators

1. **Zero Browser Overhead:** By employing HTTP/2 connection pooling with Scrapling, memory footprint stays under 15MB, eliminating heavy Chromium/Playwright resource leaks.
2. **Schema Invariant Enforcement:** Raw HTML strings are validated and typed via Pydantic v2 prior to export, rejecting partial or corrupted records before client delivery.
3. **Executive Presentation Out of the Box:** The generated Excel workbook is ready for presentation without manual adjustments: headers are locked, auto-filters are active, and cell widths are computed based on actual content length.

## Tech Stack

- **HTTP Engine:** Scrapling 0.3.9 (HTTP/2 Fetcher with fallback to Requests)
- **Parser:** BeautifulSoup4 (HTML5 tree navigation)
- **Data Validation:** Pydantic v2.10
- **Columnar Engine:** PyArrow 19.0 (Snappy Parquet compression)
- **Spreadsheet Engine:** openpyxl 3.1 (custom styling, cell formatting, freeze panes)
- **Runtime:** Python 3.11

## Author

**Sk Ashfaq Bux**  
GitHub: [github.com/Albidox](https://github.com/Albidox)
