"""Comprehensive Pytest Test Suite for Artifact D8 Round 2 Stress Probe.

Engineered by Eric, Lead Software Engineering Specialist.
Asserts:
1. 500-render soak test memory bound (<300MB) and zero zombie Chromium processes.
2. Non-Latin Unicode rendering without tofu boxes (Chinese, Cyrillic, Devanagari).
3. 500-line-item massive table pagination (>= 15 pages) with verified running footers.
4. Complete SHA-256 integrity across output manifest.
5. Strict zero em dash enforcement across all code, tests, reports, and manifests.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import pytest
import pymupdf

from batch_render import compute_file_sha256, BASE_DIR

OUTPUT_DIR = BASE_DIR / "output"
STRESS_METRICS_FILE = OUTPUT_DIR / "pdf_stress_metrics.json"
REPORT_MD_FILE = OUTPUT_DIR / "playwright_pdf_stress_report.md"
MASSIVE_PDF_FILE = OUTPUT_DIR / "invoice_500_line_items.pdf"
UNICODE_PDF_FILE = OUTPUT_DIR / "invoice_unicode_stress.pdf"
SHA256_FILE = OUTPUT_DIR / "SHA256SUMS.txt"


def test_stress_metrics_json_contract():
    """Verify presence and schema compliance of stress metrics JSON."""
    assert STRESS_METRICS_FILE.exists(), f"Missing {STRESS_METRICS_FILE}"
    with open(STRESS_METRICS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "soak_probe" in data
    assert "unicode_probe" in data
    assert "massive_table_probe" in data


def test_zombie_and_leak_probe_contract():
    """Verify 500-render soak test, memory bounding (<300MB), and zero zombie processes."""
    with open(STRESS_METRICS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    soak = data["soak_probe"]
    assert soak["total_renders"] == 500
    assert soak["throughput_renders_per_sec"] > 5.0, "Throughput fell below 5.0 renders/sec"

    # Memory bounding
    mem = soak["memory_metrics_mb"]
    assert mem["peak_daemon_rss_mb"] < 300.0, f"Daemon RAM exceeded 300MB: {mem['peak_daemon_rss_mb']}MB"
    assert mem["ram_bounded_strictly"] is True

    # Zombie audit
    zomb = soak["zombie_audit"]
    assert zomb["lingering_zombies_count"] == 0
    assert len(zomb["remaining_child_pids"]) == 0
    assert zomb["zero_zombies_verified"] is True


def test_unicode_glyph_fidelity_and_zero_tofu():
    """Verify non-Latin Unicode rendering, zero tofu boxes, and embedded fonts."""
    assert UNICODE_PDF_FILE.exists(), f"Missing {UNICODE_PDF_FILE}"
    doc = pymupdf.open(UNICODE_PDF_FILE)
    assert len(doc) >= 1

    all_text = "".join(doc[pno].get_text() for pno in range(len(doc)))
    clean_all = re.sub(r"\s+", "", all_text)

    # 1. Assert zero tofu boxes (U+FFFD)
    assert "\ufffd" not in all_text, "Found tofu box (U+FFFD) in extracted Unicode text!"

    # 2. Assert Chinese glyphs present
    chinese_keywords = ["北京分布式系统科技", "分布式高可用共识算法状态机", "大规模云原生微服务"]
    for kw in chinese_keywords:
        assert re.sub(r"\s+", "", kw) in clean_all, f"Missing Chinese keyword: {kw}"

    # 3. Assert Cyrillic glyphs present
    cyrillic_keywords = ["ОООАпекс", "Высоконагруженнаярепликация", "ЯндексТехнологии"]
    for kw in cyrillic_keywords:
        assert re.sub(r"\s+", "", kw) in clean_all, f"Missing Cyrillic keyword: {kw}"

    # 4. Assert Devanagari glyphs present
    devanagari_keywords = ["एपेक्स", "वितरित", "डेटाबेस", "विभाजन", "टाटा"]
    for kw in devanagari_keywords:
        assert kw in clean_all, f"Missing Devanagari keyword: {kw}"

    # 5. Assert embedded fonts for complex scripts
    embedded_fonts = set()
    for pno in range(len(doc)):
        for f in doc[pno].get_fonts():
            embedded_fonts.add(f[3])
    doc.close()

    font_names = " ".join(embedded_fonts)
    assert "NirmalaUI" in font_names or "Mangal" in font_names, "Missing Devanagari font embedding"
    assert "MicrosoftYaHei" in font_names or "SimSun" in font_names or "SimHei" in font_names, "Missing Chinese font embedding"


def test_massive_table_pagination_and_running_footers():
    """Verify 500-line-item invoice pagination (>=15 pages) and running footers."""
    assert MASSIVE_PDF_FILE.exists(), f"Missing {MASSIVE_PDF_FILE}"
    doc = pymupdf.open(MASSIVE_PDF_FILE)
    total_pages = len(doc)

    # Must span 15+ pages
    assert total_pages >= 15, f"Expected >= 15 pages for 500 items, got {total_pages}"
    assert total_pages == 32, f"Expected exactly 32 pages for 500 items, got {total_pages}"

    clipping_errors = []
    footer_matches = 0

    with open(STRESS_METRICS_FILE, "r", encoding="utf-8") as f:
        metrics = json.load(f)
    pages_summary = metrics["massive_table_probe"]["pages_summary"]

    for pno in range(total_pages):
        page = doc[pno]
        rect = page.rect
        blocks = page.get_text("blocks")
        text = page.get_text()

        # Check for vertical boundary clipping
        for b in blocks:
            x0, y0, x1, y1, t, bno, btype = b
            if y0 < 0 or y1 > rect.height + 1.0:
                clipping_errors.append(f"Page {pno + 1} text clipping: y0={y0}, y1={y1}")

        # Check running footer cumulative total
        expected_cum = pages_summary[pno]["cumulative_total"]
        cum_str_1 = f"{expected_cum:,.2f}"
        cum_str_2 = f"{expected_cum:.2f}"
        if cum_str_1 in text or cum_str_2 in text:
            footer_matches += 1

    doc.close()

    assert len(clipping_errors) == 0, f"Found {len(clipping_errors)} text clipping errors"
    assert footer_matches == total_pages, f"Running footer totals matched on {footer_matches}/{total_pages} pages"


def test_stress_report_existence_and_content():
    """Verify output/playwright_pdf_stress_report.md exists and contains audit sections."""
    assert REPORT_MD_FILE.exists(), f"Missing {REPORT_MD_FILE}"
    with open(REPORT_MD_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    assert "# Artifact D8 Round 2: Real-World Stress Probe and Zombie Process Audit Report" in content
    assert "Executive Summary" in content
    assert "Probe 1: Zombie Tab and Memory Leak Soak Probe" in content
    assert "Probe 2: Missing Font and Non-Latin Unicode Probe" in content
    assert "Probe 3: Massive Table Stress Test (500 Line Items)" in content
    assert "Epistemic Verification and Defense in Depth" in content


def test_sha256_manifest_integrity():
    """Verify output/SHA256SUMS.txt contains all artifacts with 100% hash match."""
    assert SHA256_FILE.exists(), f"Missing {SHA256_FILE}"
    with open(SHA256_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) >= 54, f"Expected at least 54 entries in SHA256SUMS.txt, found {len(lines)}"

    for line in lines:
        expected_hash, rel_path = line.split(maxsplit=1)
        full_path = OUTPUT_DIR / rel_path
        assert full_path.exists(), f"Manifest lists missing file: {full_path}"
        actual_hash = compute_file_sha256(full_path)
        assert actual_hash == expected_hash, f"Hash mismatch for {rel_path}: expected {expected_hash}, got {actual_hash}"


def test_zero_em_dashes_enforcement():
    """Scan all project code, templates, reports, and manifests for em dash violations."""
    files_to_check = [
        REPORT_MD_FILE,
        STRESS_METRICS_FILE,
        SHA256_FILE,
        BASE_DIR / "pdf_generator.py",
        BASE_DIR / "batch_render.py",
        BASE_DIR / "stress_probe.py",
        BASE_DIR / "templates" / "invoice.html",
        BASE_DIR / "tests" / "test_pdf_daemon.py",
        BASE_DIR / "tests" / "test_stress_probe.py",
    ]

    em_dash_char = chr(0x2014)
    violations = []

    for file_path in files_to_check:
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if em_dash_char in content:
                    violations.append(str(file_path.relative_to(BASE_DIR)))

    assert len(violations) == 0, f"Em dashes detected in files: {violations}"
