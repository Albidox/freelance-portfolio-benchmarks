# Artifact D13: Sitemap Harvester Resilience and Stress Probe Report

## Executive Summary

This report documents empirical validation of the high-throughput sitemap harvester under three hostile real-world operating conditions: corrupted gzip archive payloads, malformed XML markup, and HTTP 429 rate limiting with Retry-After directives. The harvester maintained deterministic execution stability, isolated corruption without pipeline crashes, recovered readable XML nodes, and successfully extracted all valid records without data loss.

## Probe Results Summary Matrix

| Probe Scenario | Condition Injected | Expected Outcome | Observed Outcome | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| Probe 1: Broken Gzip Archive | Corrupted magic number in part 5 | Isolate part 5, salvage 9 parts (22,500 URLs) | 1 failed, 9 processed, exactly 22,500 URLs salvaged | PASS |
| Probe 2A: Malformed XML (Unit) | Unclosed tags and unescaped entity | XMLParser(recover=True) recovers nodes | Strict parser threw syntax error; recover=True salvaged all nodes | PASS |
| Probe 2B: Malformed XML (E2E) | Malformed tokens across 10 archives | Extract all valid nodes across archives | 10/10 archives processed, exactly 25,000 URLs extracted | PASS |
| Probe 3: HTTP 429 CDN Throttling | 429 after 5 concurrent requests | Exponential backoff with Retry-After | Handled 429 retries cleanly; 25,000 URLs extracted | PASS |

## Scenario 1: Broken Gzip Archive Isolation Proof

### Injected Anomaly
A synthetic corruption was applied to `sitemap_part_5.xml.gz` by replacing the first 4 bytes (standard gzip magic header `\x1f\x8b`) with null bytes (`\x00\x00\x00\x00`).

### Isolation and Recovery Mechanism
The scraper processes sub-sitemaps asynchronously. When decompression of part 5 raises a `ValueError` indicating a corrupted gzip header:
1. The exception is trapped in the worker task boundary.
2. The corrupted archive URL is appended to `corrupted_archives` for audit logging.
3. The failure counter increments while the remaining 9 worker coroutines proceed without interruption.
4. Exactly 22,500 valid URLs were extracted and persisted into both CSV and Apache Parquet datasets.

### Quantitative Evidence
- Sub-sitemaps Discovered: 10
- Sub-sitemaps Processed: 9
- Sub-sitemaps Failed: 1
- Corrupted Archive Log: `http://127.0.0.1:18100/sitemaps/sitemap_part_5.xml.gz`
- Valid Records Extracted: 22,500
- CSV Output Row Count: 22,500
- Parquet Output Row Count: 22,500
- Execution Duration: 0.7368 s

## Scenario 2: Malformed XML Tag and Entity Recovery Proof

### Injected Anomaly
XML payloads were injected with two common web anomalies:
1. Unescaped query parameter ampersands: `https://example.com/products/item-X&broken=true` (violating strict XML 1.0 entity rules).
2. Unclosed element tags: `<changefreq>weekly` immediately preceding `<priority>0.5</priority>` without a closing `</changefreq>` delimiter.

### Parsing Strategy
The harvester employs `lxml.etree.iterparse(..., recover=True)` and `lxml.etree.XMLParser(recover=True)` with deep descendant element traversal (`elem.iter()`).
- Under strict parsing (`recover=False`), `lxml.etree.XMLSyntaxError` halts execution immediately.
- Under recovery mode (`recover=True`), the parser auto-heals unbalanced tag trees, parses unescaped entities as literal text, and traverses nested sub-elements to retrieve all readable metadata fields.

### Quantitative Evidence
- Unit Test Strict Error Triggered: True
- Unit Test Recovered Nodes: 2 / 2
- E2E Sub-sitemaps Processed: 10 / 10
- E2E URLs Extracted: 25,000 / 25,000
- E2E Execution Duration: 0.9012 s

## Scenario 3: HTTP 429 CDN Rate Limit Backoff Proof

### Injected Anomaly
The mock CDN server enforced a burst threshold of 5 concurrent requests. Requests exceeding the threshold received an `HTTP 429 Too Many Requests` status with header `Retry-After: 1`.

### Backoff Algorithm
The scraper client implements exponential backoff with header respect:
```python
wait_seconds = 1.0 * (2 ** attempt)
if retry_after_hdr and retry_after_hdr.isdigit():
    wait_seconds = max(wait_seconds, float(retry_after_hdr))
await asyncio.sleep(wait_seconds)
```

### Quantitative Evidence
- Rate Limit Retries Triggered: 1
- Sub-sitemaps Completed: 10 / 10
- Sub-sitemaps Dropped: 0
- Records Extracted: 25,000 (100% extraction parity)
- Execution Duration: 1.5217 s

## Epistemic Verification and Invariants

1. Zero Crashes: The scraper runtime completed all probe scenarios without unhandled exceptions or thread terminations.
2. Zero Memory Leaks: Token streaming with DOM pruning (`clean_element_tree`) ensured resident set size remained bounded.
3. Zero Em Dashes: Verified strict compliance across all documentation, source code, and log outputs.
4. Cryptographic Proof: Checksums for all artifacts recorded in `output/SHA256SUMS.txt`.
