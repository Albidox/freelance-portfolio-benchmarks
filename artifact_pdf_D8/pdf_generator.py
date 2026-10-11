"""Headless Browser PDF and Screenshot Daemon.

Engineered by Eric, Backend and Distributed Systems Specialist.
Provides pooled Playwright browser lifecycle management for rendering
pixel-perfect A4 invoices and 1200x630 OpenGraph social previews.
"""

from __future__ import annotations

import asyncio
import gc
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
import psutil

# Optimize Node.js driver memory footprint for Playwright on Windows
os.environ.setdefault("NODE_OPTIONS", "--max-old-space-size=48")

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright


class PDFGenerator:
    """Enterprise-grade headless PDF and OpenGraph thumbnail generator daemon."""

    CHROMIUM_LAUNCH_ARGS: List[str] = [
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--renderer-process-limit=1",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-breakpad",
        "--disable-component-update",
        "--disable-domain-reliability",
        "--disable-features=AudioServiceOutOfProcess,IsolateOrigins,site-per-process,OptimizationHints",
        "--disable-hang-monitor",
        "--disable-ipc-flooding-protection",
        "--disable-popup-blocking",
        "--disable-prompt-on-repost",
        "--disable-renderer-backgrounding",
        "--disable-sync",
        "--disable-translate",
        "--metrics-recording-only",
        "--mute-audio",
        "--js-flags=--max-old-space-size=48 --optimize-for-size",
    ]

    def __init__(
        self,
        templates_dir: Optional[str | Path] = None,
        max_pool_size: int = 1,
        recycle_interval: int = 25,
    ) -> None:
        """Initialize PDFGenerator daemon configuration."""
        if templates_dir is None:
            templates_dir = Path(__file__).resolve().parent / "templates"
        self.templates_dir = Path(templates_dir)
        self.max_pool_size = max_pool_size
        self.recycle_interval = recycle_interval

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._render_count: int = 0
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> PDFGenerator:
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit with deterministic cleanup."""
        await self.close()

    async def start(self) -> None:
        """Launch Playwright and Chromium browser instance."""
        if self._browser is not None:
            return

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=self.CHROMIUM_LAUNCH_ARGS,
        )
        await self._init_context_and_page()

    async def _init_context_and_page(self) -> None:
        """Initialize or recycle the browser context and active page."""
        if self._page is not None:
            try:
                await self._page.close()
            except Exception:
                pass
            self._page = None

        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None

        if self._browser is None:
            raise RuntimeError("Chromium browser is not running.")

        self._context = await self._browser.new_context(
            viewport={"width": 1200, "height": 630},
            device_scale_factor=2,
        )
        self._page = await self._context.new_page()
        self._render_count = 0
        gc.collect()

    async def render_html(self, invoice_data: Dict[str, Any], is_thumbnail: bool = False) -> str:
        """Render HTML string from Jinja2 template."""
        template = self.jinja_env.get_template("invoice.html")
        return template.render(invoice=invoice_data, is_thumbnail=is_thumbnail)

    async def render_pdf(
        self,
        invoice_data: Dict[str, Any],
        output_path: str | Path,
    ) -> Path:
        """Render invoice to multi-page A4 PDF document with print media styles."""
        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)

        html_content = await self.render_html(invoice_data, is_thumbnail=False)

        async with self._lock:
            if self._page is None:
                await self._init_context_and_page()

            assert self._page is not None

            # Render HTML content
            await self._page.set_content(html_content, wait_until="load")

            # Playwright PDF generation with A4 dimensions and headers/footers
            pdf_bytes = await self._page.pdf(
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template=(
                    '<div style="font-size: 8px; width: 100%; display: flex; '
                    'justify-content: space-between; padding: 0 15mm; color: #64748b; '
                    'font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;">'
                    '<span>Apex Distributed Systems LLC</span>'
                    '<span>CONFIDENTIAL INVOICE</span>'
                    '</div>'
                ),
                footer_template=(
                    '<div style="font-size: 8px; width: 100%; display: flex; '
                    'justify-content: space-between; padding: 0 15mm; color: #64748b; '
                    'font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;">'
                    '<span>Apex Distributed Systems | apex.systems</span>'
                    '<span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>'
                    '</div>'
                ),
                margin={
                    "top": "15mm",
                    "bottom": "18mm",
                    "left": "15mm",
                    "right": "15mm",
                },
            )

            with open(out_file, "wb") as f:
                f.write(pdf_bytes)

            self._render_count += 1
            if self._render_count >= self.recycle_interval:
                await self._init_context_and_page()

        return out_file

    async def render_thumbnail(
        self,
        invoice_data: Dict[str, Any],
        output_path: str | Path,
    ) -> Path:
        """Render 1200x630 OpenGraph social preview screenshot."""
        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)

        html_content = await self.render_html(invoice_data, is_thumbnail=True)

        async with self._lock:
            if self._page is None:
                await self._init_context_and_page()

            assert self._page is not None

            await self._page.set_viewport_size({"width": 1200, "height": 630})
            await self._page.set_content(html_content, wait_until="load")

            screenshot_bytes = await self._page.screenshot(
                type="png",
                clip={"x": 0, "y": 0, "width": 1200, "height": 630},
            )

            with open(out_file, "wb") as f:
                f.write(screenshot_bytes)

            self._render_count += 1
            if self._render_count >= self.recycle_interval:
                await self._init_context_and_page()

        return out_file

    def get_memory_usage_mb(self) -> Dict[str, float]:
        """Inspect current resident set size (RSS) memory in megabytes."""
        current_proc = psutil.Process()
        daemon_rss = current_proc.memory_info().rss / (1024 * 1024)

        child_rss = 0.0
        for child in current_proc.children(recursive=True):
            try:
                child_rss += child.memory_info().rss / (1024 * 1024)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return {
            "daemon_rss_mb": round(daemon_rss, 2),
            "children_rss_mb": round(child_rss, 2),
            "total_rss_mb": round(daemon_rss + child_rss, 2),
        }

    async def close(self) -> None:
        """Deterministic teardown of page, context, browser, and playwright driver."""
        if self._page is not None:
            try:
                await self._page.close()
            except Exception:
                pass
            self._page = None

        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None

        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        gc.collect()
