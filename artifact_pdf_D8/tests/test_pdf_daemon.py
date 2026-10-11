"""Comprehensive Unit and Integration Tests for Headless PDF and Screenshot Daemon.

Engineered by Eric, Backend and Distributed Systems Specialist.
Tests A4 PDF generation, 1200x630 OpenGraph thumbnails, PyMuPDF layout inspection,
zero table clipping, and strict zero em dash compliance.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import pymupdf

from pdf_generator import PDFGenerator
from batch_render import generate_invoice_data, BASE_DIR

TEST_OUT_DIR = BASE_DIR / "output" / "test_run"


@pytest.fixture(scope="module")
def sample_invoice():
    """Generate deterministic invoice fixture."""
    return generate_invoice_data(1)


@pytest.fixture
async def daemon():
    """Async fixture managing PDFGenerator lifecycle."""
    TEST_OUT_DIR.mkdir(parents=True, exist_ok=True)
    gen = PDFGenerator(recycle_interval=20)
    await gen.start()
    yield gen
    await gen.close()


@pytest.mark.asyncio
async def test_html_template_contract(daemon: PDFGenerator, sample_invoice):
    """Verify HTML template structure and CSS paged media rules."""
    html = await daemon.render_html(sample_invoice, is_thumbnail=False)
    assert "@page" in html
    assert "size: A4 portrait" in html
    assert "page-break-inside: avoid" in html
    assert "break-inside: avoid" in html
    assert sample_invoice["invoice_number"] in html
    assert sample_invoice["company"]["name"] in html


@pytest.mark.asyncio
async def test_pdf_generation_and_layout(daemon: PDFGenerator, sample_invoice):
    """Verify PDF dimensions, multi-page flow, and zero table row clipping."""
    pdf_path = TEST_OUT_DIR / "test_invoice.pdf"
    await daemon.render_pdf(sample_invoice, pdf_path)

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 5000

    doc = pymupdf.open(pdf_path)
    # 35 items should span across 2 or 3 pages
    assert len(doc) >= 2, f"Expected multi-page PDF, got {len(doc)} pages"

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        rect = page.rect
        # A4 portrait points: ~595.3 x ~841.9
        assert abs(rect.width - 595.3) < 2.0
        assert abs(rect.height - 841.9) < 2.0

        blocks = page.get_text("blocks")
        assert len(blocks) > 0, f"Page {page_idx + 1} has no text content"

        # Assert zero text block clipping
        for b in blocks:
            x0, y0, x1, y1, text, block_no, block_type = b
            assert y0 >= 0, f"Text clipped at top margin: y0={y0}"
            assert y1 <= rect.height + 1.0, f"Text clipped at bottom margin: y1={y1}"

    doc.close()


@pytest.mark.asyncio
async def test_thumbnail_generation(daemon: PDFGenerator, sample_invoice):
    """Verify 1200x630 OpenGraph social preview PNG dimensions and format."""
    thumb_path = TEST_OUT_DIR / "test_thumbnail.png"
    await daemon.render_thumbnail(sample_invoice, thumb_path)

    assert thumb_path.exists()
    assert thumb_path.stat().st_size > 5000

    pix = pymupdf.Pixmap(str(thumb_path))
    assert pix.width in (1200, 2400)
    assert pix.height in (630, 1260)


@pytest.mark.asyncio
async def test_memory_compliance(daemon: PDFGenerator):
    """Verify daemon RSS memory stays bounded under 250MB limit."""
    mem = daemon.get_memory_usage_mb()
    assert mem["daemon_rss_mb"] < 250.0, f"Daemon RAM exceeded: {mem['daemon_rss_mb']} MB"


def test_zero_em_dashes_enforcement():
    """Verify strict absence of em dashes across all code and template files."""
    code_extensions = [".py", ".html", ".json", ".txt", ".md"]
    target_files = []
    for ext in code_extensions:
        target_files.extend(BASE_DIR.glob(f"*{ext}"))
        target_files.extend((BASE_DIR / "templates").glob(f"*{ext}"))
        target_files.extend((BASE_DIR / "tests").glob(f"*{ext}"))
        target_files.extend((BASE_DIR / "output").glob(f"*{ext}"))

    violations = []
    for f in target_files:
        if not f.is_file():
            continue
        try:
            content = f.read_text(encoding="utf-8")
            if "\u2014" in content:
                violations.append(str(f.relative_to(BASE_DIR)))
        except Exception:
            pass

    assert not violations, f"Em dash violations found in files: {violations}"
