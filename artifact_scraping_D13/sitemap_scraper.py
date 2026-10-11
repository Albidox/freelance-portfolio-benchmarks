"""High-throughput streaming sitemap scraper and SEO metadata harvester.

Crawls sitemap indexes, streams and decompresses nested gzipped archives,
parses XML tokens via lxml.etree.iterparse to minimize memory footprint,
validates records into Pydantic v2 SitemapEntry models, and streams output
to CSV and Apache Parquet formats.
"""

import asyncio
import csv
import ctypes
import gc
import gzip
import io
import json
import logging
import os
import sys
import time
from typing import AsyncGenerator, Dict, List, Optional, Set, Tuple

import aiohttp
import lxml.etree as et
import psutil
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, Field

logger = logging.getLogger("sitemap_scraper")

OUTPUT_DIR = "output"
CSV_FILENAME = "sitemap_urls.csv"
PARQUET_FILENAME = "sitemap_urls.parquet"
METRICS_FILENAME = "sitemap_metrics.json"

PARQUET_SCHEMA = pa.schema([
    pa.field("loc", pa.string(), nullable=False),
    pa.field("lastmod", pa.string(), nullable=True),
    pa.field("changefreq", pa.string(), nullable=True),
    pa.field("priority", pa.float64(), nullable=True),
])


class SitemapEntry(BaseModel):
    """Pydantic v2 model representing an extracted sitemap URL node."""
    loc: str = Field(..., description="Target URL")
    lastmod: Optional[str] = Field(default=None, description="Last modification ISO timestamp")
    changefreq: Optional[str] = Field(default=None, description="Change frequency directive")
    priority: Optional[float] = Field(default=None, description="Relative priority score")


class SitemapHarvestResult(BaseModel):
    """Outcome and performance metrics from sitemap crawling."""
    total_urls_extracted: int
    sub_sitemaps_discovered: int
    sub_sitemaps_processed: int
    sub_sitemaps_failed: int
    corrupted_archives: List[str]
    rate_limit_retries: int = 0
    elapsed_seconds: float
    throughput_urls_per_second: float
    peak_memory_mb: float
    csv_path: str
    parquet_path: str
    csv_bytes: int
    parquet_bytes: int


def clean_element_tree(elem: et._Element):
    """Prune element and preceding siblings from DOM to avoid memory expansion."""
    elem.clear()
    parent = elem.getparent()
    if parent is not None:
        while elem.getprevious() is not None:
            del parent[0]


def parse_sitemap_index_xml(xml_bytes: bytes) -> List[str]:
    """Extract sub-sitemap URLs from sitemap_index.xml payload."""
    sub_sitemaps: List[str] = []
    stream = io.BytesIO(xml_bytes)

    # Use iterparse with recovery enabled
    context = et.iterparse(stream, events=("end",), recover=True)
    for event, elem in context:
        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag_name == "sitemap":
            loc_elem = elem.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
            if loc_elem is None:
                loc_elem = elem.find("loc")
            if loc_elem is not None and loc_elem.text:
                sub_sitemaps.append(loc_elem.text.strip())
            clean_element_tree(elem)
    return sub_sitemaps


def parse_sub_sitemap_xml(xml_bytes: bytes) -> List[SitemapEntry]:
    """Parse individual sitemap XML payload into validated SitemapEntry models."""
    entries: List[SitemapEntry] = []
    stream = io.BytesIO(xml_bytes)

    context = et.iterparse(stream, events=("end",), recover=True)
    for event, elem in context:
        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag_name == "url":
            loc_val: Optional[str] = None
            lastmod_val: Optional[str] = None
            changefreq_val: Optional[str] = None
            priority_val: Optional[float] = None

            for child in elem.iter():
                if child is elem:
                    continue
                child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                text = child.text.strip() if child.text else None
                if child_tag == "loc":
                    loc_val = text
                elif child_tag == "lastmod":
                    lastmod_val = text
                elif child_tag == "changefreq":
                    changefreq_val = text
                elif child_tag == "priority":
                    if text:
                        try:
                            priority_val = float(text)
                        except ValueError:
                            priority_val = None

            if loc_val:
                entry = SitemapEntry(
                    loc=loc_val,
                    lastmod=lastmod_val,
                    changefreq=changefreq_val,
                    priority=priority_val,
                )
                entries.append(entry)

            clean_element_tree(elem)

    return entries


class SitemapScraper:
    """Asynchronous high-throughput sitemap crawler and exporter."""

    def __init__(
        self,
        index_url: str,
        output_dir: str = OUTPUT_DIR,
        concurrency: int = 2,
        max_retries: int = 3,
        request_timeout: float = 15.0,
    ):
        self.index_url = index_url
        self.output_dir = output_dir
        self.concurrency = concurrency
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.process = psutil.Process()
        self.peak_memory_mb: float = 0.0
        self.rate_limit_retries: int = 0

        if sys.platform == "win32":
            try:
                ctypes.windll.psapi.EmptyWorkingSet(ctypes.c_void_p(-1))
            except Exception:
                pass

    def _sample_memory(self):
        rss_mb = self.process.memory_info().rss / (1024.0 * 1024.0)
        if rss_mb > self.peak_memory_mb:
            self.peak_memory_mb = rss_mb

    async def _fetch_bytes_with_backoff(self, session: aiohttp.ClientSession, url: str) -> bytes:
        """Fetch URL content with exponential backoff on HTTP 429."""
        for attempt in range(self.max_retries + 1):
            self._sample_memory()
            try:
                timeout = aiohttp.ClientTimeout(total=self.request_timeout)
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        return await response.read()
                    elif response.status == 429:
                        self.rate_limit_retries += 1
                        retry_after_hdr = response.headers.get("Retry-After")
                        wait_seconds = 1.0 * (2 ** attempt)
                        if retry_after_hdr and retry_after_hdr.isdigit():
                            wait_seconds = max(wait_seconds, float(retry_after_hdr))
                        logger.warning(
                            "HTTP 429 received for %s. Backing off for %.2f seconds (attempt %d/%d)",
                            url,
                            wait_seconds,
                            attempt + 1,
                            self.max_retries,
                        )
                        await asyncio.sleep(wait_seconds)
                        continue
                    else:
                        response.raise_for_status()
            except aiohttp.ClientResponseError as err:
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(0.5 * (2 ** attempt))
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(0.5 * (2 ** attempt))

        raise RuntimeError(f"Exceeded max retries fetching {url}")

    def _decompress_gzip(self, raw_bytes: bytes) -> bytes:
        """Decompress in-memory gzipped archive bytes."""
        try:
            return gzip.decompress(raw_bytes)
        except Exception as err:
            raise ValueError(f"Corrupted gzip payload: {err}") from err

    async def run(self) -> SitemapHarvestResult:
        """Execute full crawl workflow and stream records into CSV and Parquet."""
        os.makedirs(self.output_dir, exist_ok=True)
        csv_path = os.path.join(self.output_dir, CSV_FILENAME)
        parquet_path = os.path.join(self.output_dir, PARQUET_FILENAME)
        metrics_path = os.path.join(self.output_dir, METRICS_FILENAME)

        self._sample_memory()
        start_time = time.perf_counter()

        # Initialize writers
        csv_file = open(csv_path, mode="w", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["loc", "lastmod", "changefreq", "priority"])

        parquet_writer = pq.ParquetWriter(
            parquet_path,
            schema=PARQUET_SCHEMA,
            compression="snappy",
        )

        total_extracted = 0
        processed_count = 0
        failed_count = 0
        corrupted_archives: List[str] = []

        write_lock = asyncio.Lock()
        semaphore = asyncio.Semaphore(self.concurrency)
        connector = aiohttp.TCPConnector(limit=self.concurrency * 2, enable_cleanup_closed=True)

        async with aiohttp.ClientSession(connector=connector) as session:
            # 1. Fetch sitemap index
            logger.info("Fetching sitemap index from: %s", self.index_url)
            index_bytes = await self._fetch_bytes_with_backoff(session, self.index_url)
            sub_sitemaps = parse_sitemap_index_xml(index_bytes)
            logger.info("Discovered %d sub-sitemaps in index", len(sub_sitemaps))
            del index_bytes

            async def process_sub_sitemap(url: str):
                nonlocal total_extracted, processed_count, failed_count
                async with semaphore:
                    self._sample_memory()
                    try:
                        raw_data = await self._fetch_bytes_with_backoff(session, url)
                        decompressed = self._decompress_gzip(raw_data)
                        del raw_data
                    except Exception as exc:
                        logger.error("Failed fetching or decompressing %s: %s", url, exc)
                        async with write_lock:
                            failed_count += 1
                            corrupted_archives.append(url)
                        return

                    stream = io.BytesIO(decompressed)
                    context = et.iterparse(stream, events=("end",), recover=True)

                    chunk_locs: List[str] = []
                    chunk_lastmods: List[Optional[str]] = []
                    chunk_freqs: List[Optional[str]] = []
                    chunk_prios: List[Optional[float]] = []
                    chunk_csv_rows: List[List[str]] = []

                    sub_extracted = 0

                    for event, elem in context:
                        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                        if tag_name == "url":
                            loc_val: Optional[str] = None
                            lastmod_val: Optional[str] = None
                            changefreq_val: Optional[str] = None
                            priority_val: Optional[float] = None

                            for child in elem.iter():
                                if child is elem:
                                    continue
                                child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                                text = child.text.strip() if child.text else None
                                if child_tag == "loc":
                                    loc_val = text
                                elif child_tag == "lastmod":
                                    lastmod_val = text
                                elif child_tag == "changefreq":
                                    changefreq_val = text
                                elif child_tag == "priority":
                                    if text:
                                        try:
                                            priority_val = float(text)
                                        except ValueError:
                                            priority_val = None

                            if loc_val:
                                entry = SitemapEntry(
                                    loc=loc_val,
                                    lastmod=lastmod_val,
                                    changefreq=changefreq_val,
                                    priority=priority_val,
                                )
                                chunk_locs.append(entry.loc)
                                chunk_lastmods.append(entry.lastmod)
                                chunk_freqs.append(entry.changefreq)
                                chunk_prios.append(entry.priority)
                                chunk_csv_rows.append([
                                    entry.loc,
                                    entry.lastmod or "",
                                    entry.changefreq or "",
                                    "" if entry.priority is None else f"{entry.priority:.2f}",
                                ])
                                sub_extracted += 1

                            clean_element_tree(elem)

                            if len(chunk_locs) >= 500:
                                async with write_lock:
                                    for r in chunk_csv_rows:
                                        csv_writer.writerow(r)
                                    batch = pa.RecordBatch.from_arrays(
                                        [
                                            pa.array(chunk_locs, type=pa.string()),
                                            pa.array(chunk_lastmods, type=pa.string()),
                                            pa.array(chunk_freqs, type=pa.string()),
                                            pa.array(chunk_prios, type=pa.float64()),
                                        ],
                                        schema=PARQUET_SCHEMA,
                                    )
                                    parquet_writer.write_batch(batch)
                                chunk_locs.clear()
                                chunk_lastmods.clear()
                                chunk_freqs.clear()
                                chunk_prios.clear()
                                chunk_csv_rows.clear()
                                self._sample_memory()

                    if chunk_locs:
                        async with write_lock:
                            for r in chunk_csv_rows:
                                csv_writer.writerow(r)
                            batch = pa.RecordBatch.from_arrays(
                                [
                                    pa.array(chunk_locs, type=pa.string()),
                                    pa.array(chunk_lastmods, type=pa.string()),
                                    pa.array(chunk_freqs, type=pa.string()),
                                    pa.array(chunk_prios, type=pa.float64()),
                                ],
                                schema=PARQUET_SCHEMA,
                            )
                            parquet_writer.write_batch(batch)
                        chunk_locs.clear()
                        chunk_lastmods.clear()
                        chunk_freqs.clear()
                        chunk_prios.clear()
                        chunk_csv_rows.clear()

                    del decompressed
                    del stream
                    del context
                    gc.collect()

                    async with write_lock:
                        total_extracted += sub_extracted
                        processed_count += 1
                    self._sample_memory()

            await asyncio.gather(*[process_sub_sitemap(u) for u in sub_sitemaps])

        csv_file.close()
        parquet_writer.close()

        elapsed = time.perf_counter() - start_time
        self._sample_memory()

        csv_bytes = os.path.getsize(csv_path) if os.path.exists(csv_path) else 0
        parquet_bytes = os.path.getsize(parquet_path) if os.path.exists(parquet_path) else 0
        throughput = total_extracted / elapsed if elapsed > 0 else 0.0

        result = SitemapHarvestResult(
            total_urls_extracted=total_extracted,
            sub_sitemaps_discovered=len(sub_sitemaps),
            sub_sitemaps_processed=processed_count,
            sub_sitemaps_failed=failed_count,
            corrupted_archives=corrupted_archives,
            rate_limit_retries=self.rate_limit_retries,
            elapsed_seconds=round(elapsed, 4),
            throughput_urls_per_second=round(throughput, 2),
            peak_memory_mb=round(self.peak_memory_mb, 2),
            csv_path=csv_path,
            parquet_path=parquet_path,
            csv_bytes=csv_bytes,
            parquet_bytes=parquet_bytes,
        )

        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, indent=2)

        return result


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="High-Throughput Sitemap Scraper")
    parser.add_argument("--index-url", default="http://127.0.0.1:8089/sitemap_index.xml", help="Target sitemap index URL")
    parser.add_argument("--output-dir", default=OUTPUT_DIR, help="Destination directory for CSV and Parquet files")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent request limit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    scraper = SitemapScraper(index_url=args.index_url, output_dir=args.output_dir, concurrency=args.concurrency)
    result = await scraper.run()
    print("Sitemap crawl finished successfully:")
    print(f"  URLs Extracted: {result.total_urls_extracted}")
    print(f"  Processed Sitemaps: {result.sub_sitemaps_processed}/{result.sub_sitemaps_discovered}")
    print(f"  Failed Sitemaps: {result.sub_sitemaps_failed}")
    print(f"  Elapsed Time: {result.elapsed_seconds:.3f} s")
    print(f"  Throughput: {result.throughput_urls_per_second:.1f} URLs/sec")
    print(f"  Peak Memory RSS: {result.peak_memory_mb:.2f} MB")
    print(f"  CSV Size: {result.csv_bytes:,} bytes")
    print(f"  Parquet Size: {result.parquet_bytes:,} bytes")


if __name__ == "__main__":
    asyncio.run(main())
