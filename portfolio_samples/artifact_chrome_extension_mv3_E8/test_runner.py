"""Cross-platform Python test runner verifying DOM parsing logic, RFC 4180 escaping, and manifest validity.
Executes deterministic assertions and reports verification metrics.
"""
import sys
import os
import json
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.manifest_validator import ManifestValidator
from src.content_scraper import DOMContentScraper
from src.exporter import DataExporter
import run_tests


def run_comprehensive_runner():
    print("=" * 70)
    print("RUNNING E8 TEST RUNNER (DOM PARSER, ESCAPING, MANIFEST VALIDATOR)")
    print("=" * 70)

    # 1. Manifest Validator Checks
    print("[1/3] Validating Manifest V3 Configuration...")
    validator = ManifestValidator()
    spec = validator.get_manifest_v3_spec()
    valid, errors = validator.validate_manifest(spec)
    assert valid, f"Manifest V3 invalid: {errors}"
    assert spec["manifest_version"] == 3
    assert "service_worker" in spec["background"]
    print("  -> Manifest V3 valid with zero legacy MV2 keys.")

    # Also check actual manifest.json file on disk if it exists
    manifest_path = os.path.join(CURRENT_DIR, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            disk_manifest = json.load(f)
        d_valid, d_errs = validator.validate_manifest(disk_manifest)
        assert d_valid, f"Disk manifest.json invalid: {d_errs}"
        print("  -> manifest.json on disk validated successfully.")

    # 2. DOM Parsing & Sanitization Checks
    print("[2/3] Validating Heuristic DOM Table Parsing & Formula Sanitization...")
    scraper = DOMContentScraper()
    test_html = """
    <table id="test-table">
        <tr><th>Product</th><th>Price</th><th>Formula</th></tr>
        <tr><td>Alpha Widget</td><td>$100.00</td><td>=2+2</td></tr>
        <tr><td>Beta Gadget</td><td>$250.00</td><td>+cmd|' /C calc'!A0</td></tr>
    </table>
    """
    rows = scraper.parse_html_table(test_html)
    assert len(rows) == 2
    assert rows[0]["Product"] == "Alpha Widget"
    assert rows[0]["Formula"] == "'=2+2"
    assert rows[1]["Formula"] == "'+cmd|' /C calc'!A0"
    print("  -> DOM table parsed and formulas neutralized.")

    # 3. RFC 4180 Escaping Checks
    print("[3/3] Validating RFC 4180 CSV & JSON Export Escaping...")
    exporter = DataExporter()
    escaped_comma = exporter.escape_csv_field("Alpha, Beta")
    assert escaped_comma == '"Alpha, Beta"'
    escaped_quote = exporter.escape_csv_field('Alpha "Beta"')
    assert escaped_quote == '"Alpha ""Beta"""'
    escaped_newline = exporter.escape_csv_field("Alpha\nBeta")
    assert escaped_newline == '"Alpha\nBeta"'
    print("  -> RFC 4180 escaping confirmed.")

    # 4. Invoke complete run_tests suite
    print("\nExecuting complete 26-assertion deterministic suite:")
    run_tests.main()
    print("\nTest runner execution completed successfully (100% pass rate).")


if __name__ == "__main__":
    run_comprehensive_runner()
