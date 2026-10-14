# Sk Ashfaq Bux | Java Backend & Production Database Specialist

Production Engineering Case Studies & Benchmarks: 27 Verified Backend, Database, Scraping & Automation Deliverables.

[![Repository Status](https://img.shields.io/badge/Status-Production%20Verified-success?style=flat-square)](https://github.com/Albidox/freelance-portfolio-benchmarks)
[![Java](https://img.shields.io/badge/Java-21%20LTS-orange?style=flat-square&logo=openjdk)](https://openjdk.org/)
[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.4+-brightgreen?style=flat-square&logo=springboot)](https://spring.io/projects/spring-boot)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2F%2018-blue?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![Audit Verdict](https://img.shields.io/badge/SARIF%20Audit-Zero%20Defects-blueviolet?style=flat-square)](https://github.com/Albidox/freelance-portfolio-benchmarks)

Welcome to the production engineering case study repository. This portfolio contains 27 verified, end-to-end deliverables spanning high-throughput backend services, database internals, resilient data pipelines, and infrastructure automation. Every deliverable includes reproducible benchmarks, automated regression harnesses, cryptographic checksums, and formal SARIF audit reports.

---

## Master Engineering Showcase: 27 Verified Deliverables

### 1. PostgreSQL & Database Performance

Deep-dive database engineering focusing on query planner optimization, lock contention remediation, high-volume streaming ingestion, and storage bloat elimination.

| ID | Case Study / Service | Directory | Key Technology | Verified Hero Metrics |
| :--- | :--- | :--- | :--- | :--- |
| **B1** | PostgreSQL Multi-Tenant Slow Query Optimization | [artifact_postgres_B1](./artifact_postgres_B1) | PostgreSQL, EXPLAIN BUFFERS, Composite Indexing | Query latency reduced from 115.71 ms to 5.60 ms (20.6x speedup, 95.2% latency reduction). Heap block fetches reduced from ~6,580 to 0 (100% index-only scan). Disk buffer reads dropped from 6,385 to 0. |
| **B2** | PostgreSQL Deadlock & Lock Contention Remediation | [artifact_postgres_B2](./artifact_postgres_B2) | PostgreSQL, Concurrency, Row-Level Locking | 100% deadlock elimination across 500 concurrent checkout transactions. Mean latency dropped from 1,228.07 ms to 8.91 ms (137x speedup). Zero transaction aborts under peak contention. |
| **B3** | PostgreSQL JSONB Document Profiling & Indexing | [artifact_postgres_B3](./artifact_postgres_B3) | PostgreSQL, JSONB, GIN, B-Tree Expression Indexing | Query execution time slashed from 250.18 ms baseline to 0.36 ms with functional B-Tree expression index (694x speedup) and 0.56 ms with GIN (446x speedup). Shared buffer I/O reduced by 99.86%. |
| **D1** | Flyway / Liquibase Failed Migration Zero-Downtime Repair | [artifact_db_D1](./artifact_db_D1) | Flyway 10, PostgreSQL 18, Catalog Forensics | 0.05s automated atomic metadata repair and recovery. 100% recovery verified across half-applied transactional DDL, out-of-order version conflicts, and missing migration files with zero data loss. |
| **D11** | PostgreSQL Composite & Partial Index Optimization | [artifact_db_D11](./artifact_db_D11) | PostgreSQL 18, Partial Indexes, Write Amplification | Query latency slashed from 163.43 ms to 0.096 ms (1,702x speedup) on 1,000,000 rows. Disk footprint reduced from 38.32 MB to 1.09 MB (97.1% storage savings). 100% elimination of inactive row write maintenance. |
| **D12** | Massive 500k Row Postgres Streaming COPY Ingestion Pipeline | [artifact_db_D12](./artifact_db_D12) | PostgreSQL 18, Streaming COPY, Dead-Letter Quarantine | 500,000 rows committed in 3.9519s (126,522 rows/sec); unlogged staging reached 131,350 rows/sec. Process RAM capped at 24.38 MB. Isolated malformed records into quarantine with atomic rollback on disconnect. |
| **D15** | PostgreSQL Table VACUUM & Bloat Remediation Suite | [artifact_db_D15](./artifact_db_D15) | PostgreSQL 18, Autovacuum Tuning, Online Reindexing | Dead tuple ratio eliminated from 80.39% (410,000 dead tuples) to 0.00%. Reclaimed 80.03% table disk space and 78.13% total relation space. 100,000 rows readable throughout remediation with zero downtime. |

---

### 2. Web Scraping & Data Pipelines

Industrial data extraction pipelines handling high-throughput catalog harvesting, dynamic Single-Page Application (SPA) execution, PDF document generation, and strict schema validation.

| ID | Case Study / Service | Directory | Key Technology | Verified Hero Metrics |
| :--- | :--- | :--- | :--- | :--- |
| **A1** | E-Commerce Product Scraper & Resilient Crawl Engine | [artifact_scraping_A1](./artifact_scraping_A1) | Scrapling, curl_cffi, Pydantic v2, Parquet | 1,000 product records extracted across 50 pages with 100% Pydantic v2 validation. Automated dual export to RFC 4180 CSV and Snappy Parquet with 5 styled HTML dashboard variants and SHA-256 provenance. |
| **A2** | Structured Table & Directory Data Extraction Pipeline | [artifact_scraping_A2](./artifact_scraping_A2) | Python, lxml, BeautifulSoup4, Snappy Parquet | Dynamic DOM table detection and bounded pagination across financial directories. Cleaned, type-coerced datasets exported to UTF-8 CSV, Snappy Parquet, and styled Excel (.xlsx) with SHA-256 checksums. |
| **A3** | Dynamic JavaScript / SPA Content Extraction Suite | [artifact_scraping_A3](./artifact_scraping_A3) | Camoufox, Playwright, Anti-Detection Stealth | Extracted dynamic SPA content where standard HTTP queries return 0 records. Headless stealth browser emulation successfully retrieved 100% of dynamic client-side hydrated records. |
| **D8** | Headless Chromium High-Volume PDF Report Generator | [artifact_pdf_D8](./artifact_pdf_D8) | Playwright, Chromium, Jinja2, Multilingual Unicode | 50 multi-page A4 PDFs rendered in 6.343s (7.88 invoices/sec, 150 pages). Zero table row clipping across 500-line-item 32-page documents. Daemon RSS bounded at 61.52 MB with zero zombie processes. |
| **D13** | Dynamic XML Sitemap & Gzip Index Recursive Scraper | [artifact_scraping_D13](./artifact_scraping_D13) | lxml Streaming, Gzip Parsing, HTTP 429 Backoff | 25,000 URLs extracted across 10 nested gzipped archives in 0.8190s (30,525 URLs/sec). Peak RAM bounded at 38.56 MB. Automated recovery for corrupted gzip headers and unclosed XML tags. |
| **D14** | Pydantic v2 Type Sanitizer & Quarantine Pipeline | [artifact_data_D14](./artifact_data_D14) | Pydantic v2, PyArrow, Streaming Data Cleaning | 100,000 dirty records sanitized in 2.4738s (40,423 records/sec); 1,000,000 records streamed in 15.70s under 45 MB RAM. Exactly zero uncaught exceptions. 100% invalid records isolated into dead-letter quarantine. |
| **E1** | Large-Scale B2B Directory & Multi-Million Lead Harvester | [artifact_b2b_leadgen_harvester_E1](./portfolio_samples/artifact_b2b_leadgen_harvester_E1) | Async Playwright, Scrapling, DNS MX, PostgreSQL 18 | 99.28 leads/sec crawl rate, 3,208.79 records/sec PostgreSQL 18 streaming ingestion, 99.4% RFC 5321 email accuracy, 1.50 MB peak RAM under 250 MB budget, 27/27 deterministic tests passing. |
| **E2** | Shopify & E-Commerce Catalog GraphQL Synchronization Daemon | [artifact_shopify_graphql_sync_E2](./portfolio_samples/artifact_shopify_graphql_sync_E2) | Shopify Admin GraphQL, Python 3.11, PostgreSQL 18, SQLite WAL | 29,765 variants/sec catalog sync speed, 4.39 ms / 1,000 SKUs reconciliation latency, 98.2% cost budget efficiency, 252.7 ops/sec SQLite WAL throughput, 4.73 MB peak RAM, 26/26 deterministic tests passing. |

---

### 3. Java 21 & Spring Boot 3 Modernization

Modern enterprise microservice architectures, framework migration, cache concurrency patterns, and distributed API resilience.

| ID | Case Study / Service | Directory | Key Technology | Verified Hero Metrics |
| :--- | :--- | :--- | :--- | :--- |
| **C1** | Spring Boot Hibernate N+1 Query Elimination Benchmark | [artifact_springboot_C1](./artifact_springboot_C1) | Spring Boot 3.4, Java 21 LTS, Hibernate 6, EntityGraph | SQL queries reduced from 51 to 1 (98.0% query reduction). Round-trips reduced from 51 to 1, saving 50 network traversals. Projected remote network latency reduced by 11.7x (56.46 ms to 4.83 ms). |
| **C2** | Spring Boot 2 to 3 & Spring Security 6 Modernization | [artifact_springboot_C2](./artifact_springboot_C2) | Spring Boot 3, Spring Security 6, SecurityFilterChain | Modernized legacy WebSecurityConfigurerAdapter to component-based SecurityFilterChain with authorizeHttpRequests. Clean compilation and zero deprecated DSL warnings with role-based routing. |
| **C3** | Enterprise OpenRewrite Java AST Modernization Build | [artifact_springboot_C3](./artifact_springboot_C3) | OpenRewrite 8, Jakarta EE 10, Java 21 AST Refactoring | Automated transformation of 44 import statements across 5 enterprise classes in 14.2s (99.9% manual time saved). 100% preservation of core JDK namespaces (javax.sql.DataSource). 100% green tests. |
| **D5** | Redis Cache-Aside Pattern with Stampede Lock & Circuit Breaker | [artifact_caching_D5](./artifact_caching_D5) | Spring Boot 3.4, Redis, Mutex Locking, Bloom Filter | Warm cache hit median latency of 3.032 ms (p50) with 99.50% hit ratio across 10,000 requests. KeyMutexLockManager double-checked locking ensured exactly 1 DB query under stampede. |
| **D6** | Spring Boot GraphQL Federation Gateway with DGS DataLoaders | [artifact_graphql_D6](./artifact_graphql_D6) | Spring Cloud Gateway, WebClient, RFC 7807 | 100% field parity mapping from upstream GraphQL User to Order models. Zero over-fetching via strict 5-field projection pruning. 1,000 ms timeout enforcement and RFC 7807 Problem Details on errors. |
| **D7** | Resilient HMAC-Signed Webhook Ingestion Engine | [artifact_webhook_D7](./artifact_webhook_D7) | Spring Boot 3, HMAC-SHA256, Idempotency Cache | 100 of 100 tampered payloads rejected with HTTP 401 Unauthorized. Expired replay attacks rejected in 4.31 ms. Exactly 375 unique events processed out of 500 under 25% duplicate injection. |
| **D9** | Distributed Sliding-Window Rate Limiter & Token Bucket | [artifact_ratelimit_D9](./artifact_ratelimit_D9) | Spring Boot 3, Token Bucket, RFC 6585 Headers | Strictly 10 requests allowed followed by 40 rejections (HTTP 429) at 0.127 ms rejection latency. Spoofed IP headers rejected. Zero race condition token leaks across 100 concurrent requests. |
| **D16** | Spring Security 6 Stateless RBAC Gate with JWT & RFC 7807 | [artifact_security_D16](./artifact_security_D16) | Spring Security 6, JWT, RFC 7807, StrictHttpFirewall | 100% pass rate across 53 MockMvc integration tests. Algorithm confusion attacks (alg none, unsigned tokens, rogue keys) blocked 100%. Path traversal and malicious encodings blocked by firewall. |

---

### 4. Automation & Infrastructure Ops

Operational engineering, reliable notification bots, contract testing harnesses, and build pipeline optimizations.

| ID | Case Study / Service | Directory | Key Technology | Verified Hero Metrics |
| :--- | :--- | :--- | :--- | :--- |
| **D2** | Telegram Alerts Dispatcher with Token-Bucket Rate Limiter | [artifact_bot_D2](./artifact_bot_D2) | Python, SQLite, Asyncio, Telegram Bot API | Memory footprint strictly capped beneath 45 MB RAM. Zero SQLite lock timeouts under high-concurrency ingestion. Handled network dropouts with jittered backoff; suppressed 100% duplicate alerts. |
| **D3** | OpenAPI 3.1 Mock Server & Contract-Drift Newman Regression Suite | [artifact_api_D3](./artifact_api_D3) | OpenAPI 3.1, Prism, Newman, Postman SDK | 100% test pass rate across 25 automated assertions in Newman. Collection generation completed in 0.041s. Automatically flags breaking schema contract drifts in CI pipelines. |
| **D4** | Maven Daemon (mvnd) & Multi-Stage Docker Container Optimization | [artifact_jvm_D4](./artifact_jvm_D4) | Docker Multi-Stage, jlink Custom JRE, Maven Daemon | Runtime container footprint reduced from 348 MB baseline down to 71.25 MB (79.5% reduction). Layer cache rebuild completed in 1.208s upon controller mutation. Deterministic 5,618 ms startup. |
| **D10** | Automated Integration Testing Harness with Testcontainers & Postgres | [artifact_qa_D10](./artifact_qa_D10) | Testcontainers, Spring Boot Test, PostgreSQL Container | 35 integration tests executed with 100% pass rate. Total Surefire execution finished in 9.359s (wall clock 16.312s, well within sub-20s SLA). Isolated test containers ensure zero dirty database leakage. |

---

## Architectural Principles & Quality Invariants

Every artifact in this repository adheres to strict engineering invariants:

1. **Empirical Verification Over Theory:** No performance claims exist without reproducible benchmark scripts, quantitative before-and-after metrics, and execution logs.
2. **Deterministic Resource Boundaries:** Memory footprints are strictly capped, connection pools are guarded, and background processes are deterministically cleaned up with zero zombie processes.
3. **Fail-Safe Defensive Design:** All write operations enforce idempotency, transactions use deterministic ordering to prevent deadlocks, and ingestion pipelines isolate corrupted data into dead-letter quarantines.
4. **Cryptographic Provenance:** Every artifact directory contains verified SHA256SUMS.txt manifests ensuring data integrity.
5. **SARIF Byzantine Auditing:** Deliverables are validated against static and dynamic analysis rules, codified in Oasis SARIF 2.1.0 audit reports with zero defects.

---

## Author & Contact

**Sk Ashfaq Bux**
- **Role:** Java Backend & Production Database Specialist
- **GitHub:** [@Albidox](https://github.com/Albidox)
- **Portfolio:** [sk-ashfaq-portfolio.netlify.app](https://sk-ashfaq-portfolio.netlify.app/)
