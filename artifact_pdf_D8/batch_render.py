"""Batch Render Benchmark Daemon for Headless Browser PDF and Screenshot Generation.

Engineered by Eric, Backend and Distributed Systems Specialist.
Renders 50 multi-page enterprise A4 invoices using Playwright Chromium daemon,
tracks memory and latency metrics, verifies layout via PyMuPDF, and produces
SHA-256 checksums.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List
import pymupdf
import psutil

from pdf_generator import PDFGenerator

# Directory definitions
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
INVOICES_DIR = OUTPUT_DIR / "invoices"
METRICS_FILE = OUTPUT_DIR / "pdf_metrics.json"
CHECKSUMS_FILE = OUTPUT_DIR / "SHA256SUMS.txt"
THUMBNAIL_FILE = OUTPUT_DIR / "invoice_social_preview.png"


def generate_invoice_data(index: int) -> Dict[str, Any]:
    """Generate dynamic enterprise invoice data with 35 line items for multi-page flow."""
    client_companies = [
        ("Helios Cloud Global Corp", "New York, NY", "Sarah Jenkins, VP Platform"),
        ("Vanguard Distributed Networks", "Austin, TX", "Marcus Vance, Chief Architect"),
        ("Aether Systems European Operations", "Dublin, Ireland", "Fiona Gallagher, Director SRE"),
        ("Apex Financial Infrastructure Inc", "Chicago, IL", "David Sterling, Head of Trading Systems"),
        ("Cobalt Data Processing Ltd", "London, UK", "Alistair Finch, VP Engineering"),
    ]
    client_name, client_city, contact_person = client_companies[(index - 1) % len(client_companies)]

    # Generate 35 realistic enterprise infrastructure line items
    # Ensuring every document easily spans 2 to 3 pages
    item_templates = [
        ("Distributed consensus state-machine replica verification and Byzantine audit", 480.00),
        ("High-throughput reactive event ingestion pipeline tuning and partition testing", 350.00),
        ("Native PostgreSQL read-replica connection pooling optimization via PgBouncer", 275.00),
        ("Redis cluster cache stampede mitigation via probabilistic early expiration", 320.00),
        ("Zero-downtime schema migration verification for high-concurrency order ledger", 450.00),
        ("Virtual thread concurrency soak probe under simulated 10k connections", 390.00),
        ("Distributed trace propagation audit and OpenTelemetry exporter alignment", 260.00),
    ]

    items = []
    for item_idx in range(1, 36):
        desc, unit_rate = item_templates[(item_idx - 1) % len(item_templates)]
        qty = 1 + (item_idx % 4)
        total = round(qty * unit_rate, 2)
        items.append({
            "sku": f"ENG-INF-{item_idx:03d}",
            "description": f"{desc} (Milestone {item_idx})",
            "quantity": qty,
            "unit_price": unit_rate,
            "total_price": total,
        })

    subtotal = round(sum(it["total_price"] for it in items), 2)
    tax_rate = 0.085
    tax_amount = round(subtotal * tax_rate, 2)
    shipping_fee = 125.00
    total_amount = round(subtotal + tax_amount + shipping_fee, 2)

    return {
        "invoice_number": f"INV-2026-{index:04d}",
        "issue_date": "2026-10-11",
        "due_date": "2026-11-10",
        "payment_terms": "Net 30 Days",
        "currency": "USD",
        "company": {
            "name": "Apex Distributed Systems LLC",
            "tagline": "Enterprise Cloud Architecture and Distributed Infrastructure",
            "address_line1": "100 Montgomery Street, Suite 2400",
            "city": "San Francisco, CA",
            "postal_code": "94104",
            "tax_id": "US-84-9921048",
            "email": "invoicing@apex.systems",
        },
        "client": {
            "name": client_name,
            "department": "Platform and Cloud Infrastructure Engineering",
            "contact_person": contact_person,
            "address_line1": "Enterprise Technology Plaza, Floor 12",
            "city": client_city,
            "postal_code": "10001",
            "email": f"billing@{client_name.lower().split()[0]}.io",
        },
        "remittance": {
            "bank_name": "JPMorgan Chase Bank, N.A.",
            "account_number": "**** **** 7821",
            "routing_number": "021000021",
            "swift_bic": "CHASUS33",
        },
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
        "shipping_fee": shipping_fee,
        "subtotal": subtotal,
        "total_amount": total_amount,
        "items": items,
    }


def compute_file_sha256(filepath: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


async def execute_batch_render(
    total_invoices: int = 50,
) -> Dict[str, Any]:
    """Execute batch render of invoices with resource profiling and layout verification."""
    INVOICES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Executing batch render of {total_invoices} multi-page A4 invoices...")

    peak_daemon_rss = 0.0
    peak_children_rss = 0.0
    peak_total_rss = 0.0
    render_latencies_ms: List[float] = []

    start_wall_time = time.perf_counter()

    async with PDFGenerator(recycle_interval=50) as daemon:
        # First, render representative OpenGraph social preview screenshot
        first_invoice_data = generate_invoice_data(1)
        await daemon.render_thumbnail(first_invoice_data, THUMBNAIL_FILE)

        # Batch render 50 invoices
        for i in range(1, total_invoices + 1):
            inv_data = generate_invoice_data(i)
            target_pdf = INVOICES_DIR / f"invoice_{i:03d}.pdf"

            item_start = time.perf_counter()
            await daemon.render_pdf(inv_data, target_pdf)
            item_duration_ms = (time.perf_counter() - item_start) * 1000.0
            render_latencies_ms.append(round(item_duration_ms, 2))

            mem = daemon.get_memory_usage_mb()
            if mem["daemon_rss_mb"] > peak_daemon_rss:
                peak_daemon_rss = mem["daemon_rss_mb"]
            if mem["children_rss_mb"] > peak_children_rss:
                peak_children_rss = mem["children_rss_mb"]
            if mem["total_rss_mb"] > peak_total_rss:
                peak_total_rss = mem["total_rss_mb"]

            if i % 10 == 0 or i == total_invoices:
                print(
                    f"Progress: [{i}/{total_invoices}] "
                    f"Avg Latency: {sum(render_latencies_ms) / len(render_latencies_ms):.1f}ms "
                    f"Daemon RAM: {mem['daemon_rss_mb']:.1f}MB "
                    f"Total RAM: {mem['total_rss_mb']:.1f}MB"
                )

    total_duration_sec = time.perf_counter() - start_wall_time
    avg_latency_ms = sum(render_latencies_ms) / len(render_latencies_ms)
    throughput_per_sec = total_invoices / total_duration_sec

    print(f"\nRender completed in {total_duration_sec:.2f}s ({throughput_per_sec:.2f} invoices/sec).")

    # PyMuPDF Layout Verification
    print("Executing PyMuPDF verification on all generated PDF artifacts...")
    verification_errors: List[str] = []
    total_pages_rendered = 0
    pages_per_doc: List[int] = []

    for i in range(1, total_invoices + 1):
        target_pdf = INVOICES_DIR / f"invoice_{i:03d}.pdf"
        if not target_pdf.exists():
            verification_errors.append(f"Missing PDF: {target_pdf.name}")
            continue

        doc = pymupdf.open(target_pdf)
        num_pages = len(doc)
        total_pages_rendered += num_pages
        pages_per_doc.append(num_pages)

        if num_pages < 2:
            verification_errors.append(f"Invoice {target_pdf.name} is not multi-page: {num_pages} pages")

        for pno in range(num_pages):
            page = doc[pno]
            rect = page.rect
            blocks = page.get_text("blocks")

            if len(blocks) == 0:
                verification_errors.append(f"Invoice {target_pdf.name} page {pno + 1} has zero text blocks")

            for b in blocks:
                x0, y0, x1, y1, text_block, block_no, block_type = b
                # Assert text is within page vertical bounds with 1.0 point tolerance
                if y0 < 0 or y1 > rect.height + 1.0:
                    verification_errors.append(
                        f"Invoice {target_pdf.name} page {pno + 1} text clipping: "
                        f"y0={y0:.2f}, y1={y1:.2f}, height={rect.height:.2f}"
                    )
        doc.close()

    if verification_errors:
        print(f"Verification encountered {len(verification_errors)} errors:")
        for err in verification_errors[:5]:
            print(f"  - {err}")
    else:
        print(f"PyMuPDF verification passed: {total_pages_rendered} total pages across {total_invoices} documents.")

    # Assemble Metrics Dictionary
    metrics: Dict[str, Any] = {
        "benchmark": "Headless Browser PDF & Thumbnail Generation Daemon",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "batch_size": total_invoices,
        "total_duration_seconds": round(total_duration_sec, 3),
        "target_duration_seconds": 30.0,
        "duration_compliant": total_duration_sec < 30.0,
        "throughput_invoices_per_second": round(throughput_per_sec, 2),
        "avg_latency_ms": round(avg_latency_ms, 2),
        "min_latency_ms": min(render_latencies_ms) if render_latencies_ms else 0.0,
        "max_latency_ms": max(render_latencies_ms) if render_latencies_ms else 0.0,
        "total_pages_rendered": total_pages_rendered,
        "avg_pages_per_invoice": round(total_pages_rendered / total_invoices, 2),
        "all_invoices_multi_page": all(p >= 2 for p in pages_per_doc),
        "table_row_clipping_errors": len(verification_errors),
        "zero_clipping_verified": len(verification_errors) == 0,
        "memory_metrics": {
            "peak_daemon_rss_mb": round(peak_daemon_rss, 2),
            "peak_children_rss_mb": round(peak_children_rss, 2),
            "peak_total_rss_mb": round(peak_total_rss, 2),
            "daemon_memory_limit_mb": 250.0,
            "daemon_memory_compliant": peak_daemon_rss < 250.0,
        },
        "artifacts_generated": {
            "invoices_directory": INVOICES_DIR.relative_to(BASE_DIR).as_posix(),
            "invoices_count": total_invoices,
            "social_preview_thumbnail": THUMBNAIL_FILE.relative_to(BASE_DIR).as_posix(),
        },
    }

    # Write output/pdf_metrics.json
    with open(METRICS_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved benchmark metrics to {METRICS_FILE}")

    # Generate complete SHA-256 manifest output/SHA256SUMS.txt
    print("Generating complete SHA-256 checksum manifest...")
    checksum_lines: List[str] = []

    # Hash all invoice PDFs
    for i in range(1, total_invoices + 1):
        target_pdf = INVOICES_DIR / f"invoice_{i:03d}.pdf"
        if target_pdf.exists():
            h = compute_file_sha256(target_pdf)
            rel_path = f"invoices/{target_pdf.name}"
            checksum_lines.append(f"{h}  {rel_path}")

    # Hash thumbnail
    if THUMBNAIL_FILE.exists():
        h = compute_file_sha256(THUMBNAIL_FILE)
        checksum_lines.append(f"{h}  {THUMBNAIL_FILE.name}")

    # Hash metrics file
    if METRICS_FILE.exists():
        h = compute_file_sha256(METRICS_FILE)
        checksum_lines.append(f"{h}  {METRICS_FILE.name}")

    with open(CHECKSUMS_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(checksum_lines) + "\n")
    print(f"Saved SHA-256 manifest to {CHECKSUMS_FILE} ({len(checksum_lines)} entries)")

    return metrics


def main() -> None:
    """CLI entry point for batch rendering benchmark."""
    asyncio.run(execute_batch_render(50))


if __name__ == "__main__":
    main()
