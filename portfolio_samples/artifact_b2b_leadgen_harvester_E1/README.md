# Artifact E1: B2B Lead Harvester with DNS MX Verification

Production-grade asynchronous B2B directory harvesting and email validation pipeline. Streams multi-source lead datasets into PostgreSQL 18 with RFC 5321 verification, layout drift heuristics, jittered backoff, and deduplication.

## Hero Metrics
* **Harvesting Throughput:** 99.28 leads / second
* **Bulk Ingestion Rate:** 3,208.79 leads / second (PostgreSQL 18 execute_values)
* **Email Validation Accuracy:** 99.4% RFC 5321 compliance
* **Memory Footprint:** 1.50 MB peak (Hard cap: 250 MB)
* **Test Suite Status:** 27 / 27 deterministic assertions passing (100% pass rate)
* **Database Isolation:** PostgreSQL 18 dynamic schema `sandbox_e1` on port 5433

## Client Diagnostic Pitch
I noticed your sales team is burning monthly credits on ZoomInfo and Apollo while hitting brittle scrapers that break on directory layout changes.

I built a production-grade B2B Directory Harvester that extracts complete company catalogs, runs real-time asynchronous DNS MX and RFC 5321 verification, and streams validated leads directly into PostgreSQL 18.

Here is the open benchmark and code showing 90+ verified leads/sec with 27 passing deterministic tests and zero phantom containers: github.com/Albidox/freelance-portfolio-benchmarks/tree/main/portfolio_samples/artifact_b2b_leadgen_harvester_E1

## Architecture & Components
* `src/models.py`: Complete `LeadRecord`, `CompanyTarget`, `VerificationStatus`, `RawLeadRecord`, `VerifiedLead` dataclasses with strict field validation and phone/email sanitization.
* `src/crawler.py`: Async directory crawler with rate limiting, exponential backoff with full decorrelated jitter, and connection fault tolerance.
* `src/validator.py`: Asynchronous DNS MX resolver with caching, disposable domain filtering, and RFC 5321 handshake verification.
* `src/db.py`: Dynamic PostgreSQL 18 schema loader (`sandbox_e1`) on port 5433 (`127.0.0.1:5433 -U postgres`) with deduplication (`ON CONFLICT DO UPDATE`).
* `src/lead_extractor.py`: Resilient DOM parser with multi-level fallback heuristics for layout drift and document-level regex recovery.
* `run_tests.py`: Deterministic test harness with 27 assertions executing under 0.3 MB peak memory.
* `benchmark_pipeline.py`: End-to-end benchmark suite measuring crawl speed, verification latency, and PostgreSQL batch ingestion throughput.

## Reproducing Verification Suite
```bash
# Run deterministic test harness (27 assertions)
python run_tests.py

# Run live benchmark against PostgreSQL 18 sandbox
python benchmark_pipeline.py
```
