"""Standalone deterministic test harness for E4 PDF Extractor with 26 assertions.
Runs natively on Windows without Linux shell dependencies.
Strict zero em dash policy enforced.
"""
import os
import sys
import tracemalloc
from decimal import Decimal

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.models import InvoiceLineItem, ExtractedInvoice
from src.pdf_parser import PDFLayoutParser
from src.table_extractor import TableExtractor
from src.data_cleaner import InvoiceDataCleaner
from src.config import ExtractorConfig


def test_models_and_math():
    print("Testing models and mathematical reconciliation...")
    # Assertion 1: Valid line item math
    item1 = InvoiceLineItem(
        item_description="Widget A",
        quantity=Decimal("2"),
        unit_price=Decimal("15.50"),
        total_amount=Decimal("31.00"),
    )
    assert item1.validate_math() is True, "Line item math should pass"

    # Assertion 2: Invalid line item math detected
    item2 = InvoiceLineItem(
        item_description="Widget B",
        quantity=Decimal("3"),
        unit_price=Decimal("10.00"),
        total_amount=Decimal("45.00"),
    )
    assert item2.validate_math() is False, "Invalid line item math must fail"

    # Assertion 3: Line item dictionary serializes float values
    d = item1.to_dict()
    assert d["quantity"] == 2.0 and d["total_amount"] == 31.0, "to_dict serialization failed"

    # Assertion 4: Full invoice reconciliation verification passes
    inv = ExtractedInvoice(
        invoice_number="INV-2026-001",
        invoice_date="2026-10-14",
        vendor_name="Acme Supplies Ltd",
        currency="USD",
        subtotal=Decimal("31.00"),
        tax_amount=Decimal("3.10"),
        total_due=Decimal("34.10"),
        line_items=[item1],
    )
    assert inv.verify_reconciliation() is True, "Reconciliation must pass for exact totals"

    # Assertion 5: Mathematical mismatch flagged in reconciliation
    inv_bad = ExtractedInvoice(
        invoice_number="INV-2026-002",
        invoice_date="2026-10-14",
        vendor_name="Acme Supplies Ltd",
        currency="USD",
        subtotal=Decimal("31.00"),
        tax_amount=Decimal("3.10"),
        total_due=Decimal("99.99"),
        line_items=[item1],
    )
    assert inv_bad.verify_reconciliation() is False, "Mismatch total must fail reconciliation"

    # Assertion 6: Empty line items fail reconciliation
    inv_empty = ExtractedInvoice(
        invoice_number="INV-2026-003",
        invoice_date="2026-10-14",
        vendor_name="Acme Supplies Ltd",
        currency="USD",
        subtotal=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_due=Decimal("0.00"),
        line_items=[],
    )
    assert inv_empty.verify_reconciliation() is False, "Empty items must not pass reconciliation"


def test_layout_parser():
    print("Testing PDF layout parser and word clustering...")
    parser = PDFLayoutParser(horizontal_tolerance=3.0, vertical_tolerance=2.0)

    # Assertion 7: Valid PDF stream integrity check
    valid_pdf_header = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    assert parser.inspect_stream_integrity(valid_pdf_header) is True, "Valid PDF bytes must pass"

    # Assertion 8: Truncated PDF stream detected as corrupt
    corrupt_pdf = b"%PDF-1.4\ntruncated stream without eof marker"
    assert parser.inspect_stream_integrity(corrupt_pdf) is False, "Missing EOF must be corrupt"

    # Assertion 9: Zero-byte stream detected
    assert parser.inspect_stream_integrity(b"") is False, "Empty stream must be corrupt"
    assert parser.corrupt_files_detected == 2, f"Expected 2 corrupt detections, got {parser.corrupt_files_detected}"

    # Assertion 10: Word clustering into horizontal lines
    sample_boxes = [
        {"text": "Invoice", "x0": 50.0, "top": 100.0},
        {"text": "Number", "x0": 95.0, "top": 100.2},
        {"text": "Date:", "x0": 50.0, "top": 120.0},
        {"text": "2026-10-14", "x0": 90.0, "top": 120.1},
    ]
    lines = parser.cluster_words_into_lines(sample_boxes)
    assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}"

    # Assertion 11: Word order inside line sorted by x0
    assert lines[0][0]["text"] == "Invoice" and lines[0][1]["text"] == "Number", "Line words improperly sorted"

    # Assertion 12: Column gutter detection identifies gaps
    gutters = parser.detect_column_gutters(sample_boxes)
    assert len(gutters) >= 2, f"Expected gutters detected, got {gutters}"


def test_table_extractor():
    print("Testing table extractor, header drift, and multi-line merger...")
    extractor = TableExtractor()

    raw_grid = [
        ["Description", "Qty", "Unit Price", "Total"],
        ["Dell Optiplex Workstation", "2", "650.00", "1300.00"],
        ["Extended 3-Year Hardware Support", "", "", ""],
        ["Logitech MX Master 3S Mouse", "5", "80.00", "400.00"],
    ]
    items = extractor.parse_table_grid(raw_grid)

    # Assertion 13: Item count extracted after merger
    assert len(items) == 2, f"Expected 2 merged items, got {len(items)}"

    # Assertion 14: Multi-line description properly concatenated
    assert (
        "Dell Optiplex Workstation Extended 3-Year Hardware Support" in items[0].item_description
    ), f"Multi-line merger failed: {items[0].item_description}"

    # Assertion 15: Multiline merges counter incremented
    assert extractor.multiline_merges_applied == 1, "Merges counter mismatch"

    # Assertion 16: Parsed quantity and unit price match
    assert items[0].quantity == Decimal("2") and items[0].unit_price == Decimal("650.00"), "Item 0 values mismatch"

    # Assertion 17: Header drift tolerance handles alternative names
    drift_grid = [
        ["Particulars", "Units", "Rate", "Amount"],
        ["Server Hosting Subscription", "1", "120.00", "120.00"],
    ]
    drift_items = extractor.parse_table_grid(drift_grid)
    assert len(drift_items) == 1, "Failed parsing drifted header grid"
    assert drift_items[0].total_amount == Decimal("120.00"), "Drifted amount mismatch"

    # Assertion 18: European decimal formatting parsed cleanly
    euro_val = extractor._parse_decimal("1.450,75 €")
    assert euro_val == Decimal("1450.75"), f"European decimal parse failed: {euro_val}"

    # Assertion 19: US decimal formatting parsed cleanly
    us_val = extractor._parse_decimal("$2,345.50")
    assert us_val == Decimal("2345.50"), f"US decimal parse failed: {us_val}"


def test_data_cleaner():
    print("Testing currency and date normalization...")
    cleaner = InvoiceDataCleaner()

    # Assertion 20: Currency symbol extraction
    assert cleaner.normalize_currency("Subtotal: $1,200.00") == "USD", "USD currency symbol detection failed"
    assert cleaner.normalize_currency("Gesamtbetrag: € 450,00") == "EUR", "EUR currency symbol detection failed"
    assert cleaner.normalize_currency("Amount: ₹ 25,000.00") == "INR", "INR currency symbol detection failed"

    # Assertion 21: Date normalization from standard formats
    assert cleaner.normalize_date("2026-10-14") == "2026-10-14", "ISO date normalize failed"
    assert cleaner.normalize_date("14/10/2026") == "2026-10-14", "Slash date normalize failed"
    assert cleaner.normalize_date("October 14, 2026") == "2026-10-14", "Textual month date normalize failed"

    # Assertion 22: Control characters stripped from dirty OCR text
    dirty_text = "Acme\x00Corp\x0c Invoice \x1b\x02#123"
    assert cleaner.sanitize_text(dirty_text) == "AcmeCorp Invoice #123", "Sanitize text failed to remove control bytes"

    # Assertion 23: Monetary string cleaner yields exact Decimal
    assert cleaner.clean_monetary_amount("  $ 4,567.89 USD ") == Decimal("4567.89"), "Monetary cleaner failed"

    # Assertion 24: Corrupt monetary string returns zero
    assert cleaner.clean_monetary_amount("N/A - Pending") == Decimal("0.00"), "Corrupt money should return 0.00"


def test_config_and_environment():
    print("Testing config and environment defaults...")
    cfg = ExtractorConfig()

    # Assertion 25: PostgreSQL default port aligns with Native Postgres 18
    assert cfg.db_port == 5433, f"Default port must be 5433, got {cfg.db_port}"
    assert cfg.db_schema == "e4_pdf_extractor", "Default schema mismatch"


def main():
    print("=" * 70)
    print("STARTING E4 PDF TABLE EXTRACTOR DETERMINISTIC VERIFICATION SUITE")
    print("=" * 70)
    tracemalloc.start()

    test_models_and_math()
    test_layout_parser()
    test_table_extractor()
    test_data_cleaner()
    test_config_and_environment()

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak_mem / (1024 * 1024)
    print(f"Memory Diagnostics: Peak memory consumed: {peak_mb:.2f} MB")

    # Assertion 26: Strict memory footprint ceiling under 250MB
    assert peak_mb < 250.0, f"Memory footprint exceeded 250MB: {peak_mb:.2f} MB"

    print("=" * 70)
    print("ALL 26 ASSERTIONS PASSED WITH ZERO MOCKS OR PHANTOM DAEMONS")
    print("=" * 70)


if __name__ == "__main__":
    main()
