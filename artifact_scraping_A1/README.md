# E-Commerce Product Scraper: Proof of Work

A production-grade web scraping and clean data delivery pipeline built against books.toscrape.com, featuring strict schema validation, dual-format export, and cryptographic provenance verification.

## Problem Statement

Businesses require reliable, automated data extraction from e-commerce platforms to drive pricing intelligence, monitor competitor inventory movements, and build lead generation pipelines. Unstructured or unvalidated web data frequently corrupts downstream analytical systems due to unexpected layout shifts, missing attributes, or inconsistent typing. This project demonstrates an enterprise extraction architecture that guarantees data contracts at the ingestion boundary before writing to analytical storage.

## Solution Architecture

This scraper delivers end-to-end data pipeline integrity through four core stages:

1. **Extraction:** Automated pagination across 50 catalogue pages (1,000 product records) using Scrapling's high-performance fetcher with automated fallback to standard requests.
2. **Schema Validation:** In-flight record validation using Pydantic v2 (`BookRecord`), enforcing positive non-zero pricing, 1 to 5 star rating normalization, non-empty titles, and availability parsing.
3. **Dual-Format Delivery:** Export to RFC 4180-compliant CSV and columnar Snappy-compressed Parquet via PyArrow for direct integration into OLAP warehouses.
4. **Cryptographic Provenance:** Automatic generation of SHA-256 checksums (`SHA256SUMS.txt`) and timestamped execution audit logs (`run_log.txt`) guaranteeing tamper-evident deliverables.

## Verified Run Hero Metrics

The following metrics were captured from the verified run on October 9, 2026:

- **Total Records Extracted:** 1,000 products
- **Total Pages Scraped:** 50 / 50 pages (20 items/page)
- **Validation Errors:** 0 (100% schema compliance)
- **Elapsed Runtime:** 123.90 seconds (including mandatory 1.0s polite delay between pages)
- **CSV Dataset Size:** 109,295 bytes (1,001 lines: 1 header + 1,000 data rows)
- **Parquet Dataset Size:** 72,878 bytes (Snappy compressed, columnar format)
- **CSV SHA-256:** `d0fb727eb3ab2d302608448e8fdc11ebe715fcf1efe44ca2df4aefa8f60f4874`
- **Parquet SHA-256:** `67abacafbb15d898634dd625d2eb4d5b9f602836255b7e8a5ff2cd8a2c5f2964`

## How to Run

### 1. Environment Setup

Ensure Python 3.11+ is available and install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Execute Scraper

Run the complete pipeline:

```bash
python scraper.py
```

### 3. Generate Multi-Theme Presentation Variants (Excel + HTML)

Generate the 5 bespoke styled Excel workbooks and 5 interactive HTML preview dashboards:

```bash
python generate_presentation_variants.py
```

### 4. Verify Tests and Checksums

Run complete verification suite (21 unit and deliverable tests):

```bash
pytest -v
```

Verify deliverable checksum integrity:

```bash
cd output && sha256sum -c SHA256SUMS.txt
```

## Deliverables Catalog

| File | Format | Purpose |
| :--- | :--- | :--- |
| `output/books_dataset.csv` | CSV (UTF-8, LF) | Universal tabular export (1,001 lines: header + 1,000 rows) |
| `output/books_dataset.snappy.parquet` | Apache Parquet (Snappy) | High-performance columnar storage for DuckDB/Snowflake/BigQuery |
| `output/SHA256SUMS.txt` | Checksum Manifest | Cryptographic verification hashes for dataset deliverables |
| `output/run_log.txt` | Text Log | Timestamped audit trail of all 50 page fetches and results |
| `output/excel_variants/01_corporate_slate.xlsx` | Excel (.xlsx) | Corporate Slate executive theme with zebra striping and frozen headers |
| `output/excel_variants/02_emerald_growth.xlsx` | Excel (.xlsx) | Modern SaaS Emerald theme with stock badge fills and auto-filters |
| `output/excel_variants/03_fintech_navy.xlsx` | Excel (.xlsx) | Institutional Deep Navy high-contrast financial grid theme |
| `output/excel_variants/04_minimal_monochrome.xlsx` | Excel (.xlsx) | Scandinavian Minimal Monochrome executive theme |
| `output/excel_variants/05_executive_summary_kpi.xlsx` | Excel (.xlsx) | Two-tab executive workbook with KPI cards and rating breakdown |
| `output/html_variants/01_tailwind_clean.html` | Standalone HTML | Clean Tailwind-style responsive preview with metrics and sorting |
| `output/html_variants/02_stripe_dashboard.html` | Standalone HTML | Stripe-inspired enterprise dashboard with client pagination & CSV copy |
| `output/html_variants/03_dark_fintech.html` | Standalone HTML | High-contrast dark terminal with interactive rating filter buttons |
| `output/html_variants/04_dense_analytics.html` | Standalone HTML | Bloomberg-density tabular view with sticky header & live stats footer |
| `output/html_variants/05_card_grid_hybrid.html` | Standalone HTML | Dual-mode hybrid switcher between clean table and product card grid |
| `generate_presentation_variants.py` | Python (OpenPyXL) | Standalone multi-theme presentation generator script |
| `schema.py` | Python (Pydantic v2) | Strict data contract and domain validator definition |
| `scraper.py` | Python | Extraction engine and serialization pipeline |
| `requirements.txt` | Text | Pinned package dependencies |

## Tech Stack

- **Extraction:** Scrapling 0.3.9, BeautifulSoup4 4.15.0, Requests 2.34.2
- **Validation:** Pydantic 2.10.6
- **Storage & Columnar Serialization:** PyArrow 26.0.0 (Parquet Snappy compression)
- **Runtime:** Python 3.11.16

## Author

Sk Ashfaq Bux  
GitHub: [github.com/Albidox](https://github.com/Albidox)
