"""Mock asynchronous HTTP sitemap server serving nested gzipped sitemaps.

Provides sitemap_index.xml referencing 10 sub-sitemaps (sitemap_part_1.xml.gz to
sitemap_part_10.xml.gz), each containing 2,500 URLs (25,000 URLs total).
Supports chaos injection hooks for resilience testing.
"""

import argparse
import asyncio
import gzip
import io
import logging
import socket
from typing import Dict, Optional
from aiohttp import web

logger = logging.getLogger("mock_sitemap_server")

TOTAL_PARTS = 10
URLS_PER_PART = 2500


def find_free_port(start_port: int = 18080) -> int:
    """Find an available TCP port for binding."""
    for port in range(start_port, start_port + 200):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError("No free TCP port found")


def generate_sitemap_xml_bytes(part_num: int, urls_per_part: int = URLS_PER_PART, malformed: bool = False) -> bytes:
    """Generate XML content for a single sitemap part."""
    start_idx = (part_num - 1) * urls_per_part + 1
    end_idx = part_num * urls_per_part

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for i in range(start_idx, end_idx + 1):
        freq = "daily" if i % 2 == 0 else "weekly"
        priority = "0.8" if i % 2 == 0 else "0.5"
        lastmod = f"2026-10-{(i % 28) + 1:02d}T12:00:00Z"

        if malformed and i == end_idx:
            # Inject unclosed XML tag or malformed entity for recovery testing
            lines.append(
                f"  <url>\n"
                f"    <loc>https://example.com/products/item-{i}&broken=true</loc>\n"
                f"    <lastmod>{lastmod}</lastmod>\n"
                f"    <changefreq>{freq}\n"
                f"    <priority>{priority}</priority>\n"
                f"  </url>"
            )
        else:
            lines.append(
                f"  <url>\n"
                f"    <loc>https://example.com/products/item-{i}</loc>\n"
                f"    <lastmod>{lastmod}</lastmod>\n"
                f"    <changefreq>{freq}</changefreq>\n"
                f"    <priority>{priority}</priority>\n"
                f"  </url>"
            )

    lines.append("</urlset>")
    return "\n".join(lines).encode("utf-8")


def generate_gzipped_sitemap(part_num: int, urls_per_part: int = URLS_PER_PART, corrupt_gzip: bool = False, malformed_xml: bool = False) -> bytes:
    """Compress sitemap XML into gzip bytes or inject corrupted header."""
    xml_data = generate_sitemap_xml_bytes(part_num, urls_per_part, malformed=malformed_xml)
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0.0) as gz:
        gz.write(xml_data)
    compressed = buf.getvalue()

    if corrupt_gzip:
        # Corrupt the gzip magic number header
        return b"\x00\x00\x00\x00" + compressed[4:]
    return compressed


def generate_index_xml(host: str, port: int, total_parts: int = TOTAL_PARTS) -> str:
    """Generate sitemap_index.xml referencing all sub-sitemaps."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for i in range(1, total_parts + 1):
        lines.append("  <sitemap>")
        lines.append(f"    <loc>http://{host}:{port}/sitemaps/sitemap_part_{i}.xml.gz</loc>")
        lines.append("    <lastmod>2026-10-10T12:00:00Z</lastmod>")
        lines.append("  </sitemap>")
    lines.append("</sitemapindex>")
    return "\n".join(lines)


class MockSitemapServer:
    """Asynchronous server serving synthetic sitemap datasets."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        rate_limit_enabled: bool = False,
        rate_limit_threshold: int = 5,
        corrupt_part_5: bool = False,
        malformed_xml: bool = False,
    ):
        self.host = host
        self.port = port if port is not None else find_free_port(18080)
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.cache: Dict[int, bytes] = {}
        self.rate_limit_counter: int = 0
        self.rate_limit_enabled: bool = rate_limit_enabled
        self.rate_limit_threshold: int = rate_limit_threshold
        self.corrupt_part_5: bool = corrupt_part_5
        self.malformed_xml: bool = malformed_xml
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/", self.handle_root)
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/sitemap_index.xml", self.handle_index)
        self.app.router.add_get("/sitemaps/sitemap_part_{part:[0-9]+}.xml.gz", self.handle_sitemap_part)
        self.app.router.add_post("/chaos/configure", self.handle_chaos_config)

    def preload_cache(self):
        """Pre-generate all 10 gzipped sitemaps into memory."""
        for part in range(1, TOTAL_PARTS + 1):
            self.cache[part] = generate_gzipped_sitemap(part, urls_per_part=URLS_PER_PART)

    async def handle_root(self, request: web.Request) -> web.Response:
        return web.Response(text="Mock Sitemap Server Active", content_type="text/plain")

    async def handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "healthy",
            "host": self.host,
            "port": self.port,
            "parts_available": len(self.cache),
            "urls_total": len(self.cache) * URLS_PER_PART
        })

    async def handle_chaos_config(self, request: web.Request) -> web.Response:
        """Endpoint to configure chaos simulation parameters dynamically."""
        data = await request.json()
        if "rate_limit_enabled" in data:
            self.rate_limit_enabled = bool(data["rate_limit_enabled"])
        if "rate_limit_threshold" in data:
            self.rate_limit_threshold = int(data["rate_limit_threshold"])
        if "corrupt_part_5" in data:
            self.corrupt_part_5 = bool(data["corrupt_part_5"])
        if "malformed_xml" in data:
            self.malformed_xml = bool(data["malformed_xml"])
        self.rate_limit_counter = 0
        return web.json_response({
            "rate_limit_enabled": self.rate_limit_enabled,
            "rate_limit_threshold": self.rate_limit_threshold,
            "corrupt_part_5": self.corrupt_part_5,
            "malformed_xml": self.malformed_xml
        })

    async def handle_index(self, request: web.Request) -> web.Response:
        content = generate_index_xml(self.host, self.port, TOTAL_PARTS)
        return web.Response(text=content, content_type="application/xml")

    async def handle_sitemap_part(self, request: web.Request) -> web.Response:
        part_str = request.match_info["part"]
        part = int(part_str)

        # Check rate limit simulation
        if self.rate_limit_enabled:
            self.rate_limit_counter += 1
            if self.rate_limit_counter > self.rate_limit_threshold:
                # Reset counter to emulate temporary backoff requirement
                self.rate_limit_counter = 0
                return web.Response(
                    status=429,
                    text="Too Many Requests. CDN rate limit enforced.",
                    headers={"Retry-After": "1", "Content-Type": "text/plain"}
                )

        if part < 1 or part > TOTAL_PARTS:
            return web.Response(status=404, text=f"Sitemap part {part} not found")

        # Handle chaos conditions
        if part == 5 and self.corrupt_part_5:
            data = generate_gzipped_sitemap(5, urls_per_part=URLS_PER_PART, corrupt_gzip=True)
            return web.Response(body=data, content_type="application/gzip")

        if self.malformed_xml:
            data = generate_gzipped_sitemap(part, urls_per_part=URLS_PER_PART, malformed_xml=True)
            return web.Response(body=data, content_type="application/gzip")

        if part not in self.cache:
            self.cache[part] = generate_gzipped_sitemap(part, urls_per_part=URLS_PER_PART)

        data = self.cache[part]
        return web.Response(
            body=data,
            content_type="application/gzip",
            headers={"Content-Disposition": f'attachment; filename="sitemap_part_{part}.xml.gz"'}
        )

    async def start(self):
        self.preload_cache()
        self.runner = web.AppRunner(self.app, access_log=None)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        logger.info("Mock sitemap server listening on http://%s:%d", self.host, self.port)

    async def stop(self):
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("Mock sitemap server stopped")


async def main():
    parser = argparse.ArgumentParser(description="Mock Sitemap Web Server")
    parser.add_argument("--host", default="127.0.0.1", help="Binding host")
    parser.add_argument("--port", type=int, default=8089, help="Binding port")
    parser.add_argument("--rate-limit", action="store_true", help="Enable HTTP 429 rate limiting")
    parser.add_argument("--rate-limit-threshold", type=int, default=5, help="Request threshold before 429")
    parser.add_argument("--corrupt-part-5", action="store_true", help="Inject corrupted gzip header into part 5")
    parser.add_argument("--malformed-xml", action="store_true", help="Inject malformed XML tokens into parts")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    server = MockSitemapServer(
        host=args.host,
        port=args.port,
        rate_limit_enabled=args.rate_limit,
        rate_limit_threshold=args.rate_limit_threshold,
        corrupt_part_5=args.corrupt_part_5,
        malformed_xml=args.malformed_xml,
    )
    await server.start()
    print(f"Mock Sitemap Server running at http://{args.host}:{args.port}/sitemap_index.xml")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
