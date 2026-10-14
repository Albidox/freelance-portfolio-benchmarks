"""Standalone deterministic test harness for E8 Chrome Data Exporter with 26 assertions.
Runs natively on Windows without Linux shell dependencies.
"""
import tracemalloc
import time
from src.models import (
    ExportFormat,
    JobStatus,
    ColumnMapping,
    ScrapeRule,
    BatchExportJob
)
from src.config import ExtensionExporterConfig
from src.manifest_validator import ManifestValidator
from src.background_service import BackgroundServiceWorker
from src.content_scraper import DOMContentScraper
from src.exporter import DataExporter
from src.storage import ExtensionStorage


def test_models_and_enums():
    print("Testing models and contracts...")
    job = BatchExportJob(
        job_id="job_001",
        rule_id="rule_table_01",
        format=ExportFormat.CSV,
        total_records=500,
        status=JobStatus.COMPLETED
    )

    # Assertion 1: Model serialization to dictionary
    d = job.to_dict()
    assert d["job_id"] == "job_001", "Job ID mismatch"
    assert d["format"] == "CSV", "Format serialization mismatch"

    # Assertion 2: Enum members match
    assert ExportFormat.CSV.value == "CSV"
    assert ExportFormat.JSON.value == "JSON"
    assert JobStatus.COMPLETED.value == "COMPLETED"

    # Assertion 3: ScrapeRule validation rejects missing selectors
    invalid_rule = ScrapeRule(
        rule_id="r1",
        domain_pattern="example.com",
        row_selector="",
        column_selectors={}
    )
    assert invalid_rule.validate() is False, "Empty selectors must fail validation"


def test_manifest_v3_compliance():
    print("Testing Manifest V3 schema rules and legacy V2 key prevention...")
    validator = ManifestValidator()
    manifest = validator.get_manifest_v3_spec()

    # Assertion 4: Manifest version is 3
    assert manifest["manifest_version"] == 3, "Manifest version must be 3"

    # Assertion 5: Valid Manifest V3 passes validation
    is_valid, errors = validator.validate_manifest(manifest)
    assert is_valid is True, f"Valid manifest failed with: {errors}"

    # Assertion 6: Service worker declared in background
    assert manifest["background"]["service_worker"] == "background.js"

    # Assertion 7: Action defines default_popup
    assert manifest["action"]["default_popup"] == "popup.html"

    # Assertion 8: Prohibited Manifest V2 browser_action triggers rejection
    bad_manifest = dict(manifest)
    bad_manifest["browser_action"] = {"default_popup": "popup.html"}
    is_bad_valid, bad_errors = validator.validate_manifest(bad_manifest)
    assert is_bad_valid is False, "Legacy browser_action must be rejected"
    assert any("browser_action" in e for e in bad_errors)


def test_csv_formula_injection_defense():
    print("Testing CSV formula injection sanitization...")
    scraper = DOMContentScraper()

    # Assertion 9: Formula starting with '=' is sanitized
    assert scraper.sanitize_csv_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)"

    # Assertion 10: Formula starting with '+' is sanitized
    assert scraper.sanitize_csv_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"

    # Assertion 11: Formula starting with '-' is sanitized
    assert scraper.sanitize_csv_cell("-12+45") == "'-12+45"

    # Assertion 12: Formula starting with '@' is sanitized
    assert scraper.sanitize_csv_cell("@HYPERLINK('http://evil.com')") == "'@HYPERLINK('http://evil.com')"

    # Assertion 13: Normal string without formula symbols remains untouched
    assert scraper.sanitize_csv_cell("Product SKU 99281") == "Product SKU 99281"

    # Assertion 14: Sanitize record modifies dangerous fields and increments counter
    record = {
        "title": "=1+1",
        "price": "49.99",
        "desc": "+DangerousPayload"
    }
    clean = scraper.sanitize_record(record)
    assert clean["title"] == "'=1+1"
    assert clean["price"] == "49.99"
    assert clean["desc"] == "'+DangerousPayload"
    assert scraper.sanitized_cells_count >= 2


def test_html_table_parsing():
    print("Testing HTML table heuristic extraction...")
    scraper = DOMContentScraper()
    html = """
    <table>
        <thead>
            <tr><th>Item Name</th><th>Price</th><th>Rating</th></tr>
        </thead>
        <tbody>
            <tr><td>Wireless Mouse</td><td>$29.99</td><td>4.8</td></tr>
            <tr><td>Mechanical Keyboard</td><td>$89.50</td><td>4.9</td></tr>
        </tbody>
    </table>
    """
    records = scraper.parse_html_table(html)

    # Assertion 15: Table parser extracts correct row count
    assert len(records) == 2, f"Expected 2 rows, got {len(records)}"

    # Assertion 16: Column headers mapped correctly
    assert records[0]["Item Name"] == "Wireless Mouse"
    assert records[1]["Price"] == "$89.50"


def test_rfc4180_csv_exporter():
    print("Testing RFC 4180 CSV stream formatting...")
    exporter = DataExporter()

    # Assertion 17: Fields with commas are escaped in quotes
    assert exporter.escape_csv_field("New York, NY") == '"New York, NY"'

    # Assertion 18: Fields with quotes have quotes doubled
    assert exporter.escape_csv_field('24" Monitor') == '"24"" Monitor"'

    # Assertion 19: Fields with newlines are wrapped in quotes
    assert exporter.escape_csv_field("Line 1\nLine 2") == '"Line 1\nLine 2"'

    # Assertion 20: Full CSV stream generation matches expected format
    sample_data = [
        {"name": "Laptop", "specs": '16GB RAM, 512GB SSD', "price": "999.00"},
        {"name": "Mouse", "specs": "Optical, USB", "price": "19.99"}
    ]
    csv_text = exporter.export_csv_stream(sample_data)
    assert "name,specs,price" in csv_text
    assert '"16GB RAM, 512GB SSD"' in csv_text

    # Assertion 21: Column mapping and renaming
    mappings = [
        ColumnMapping(source_field="name", target_column="Product_Title"),
        ColumnMapping(source_field="price", target_column="Cost_USD")
    ]
    mapped_csv = exporter.export_csv_stream(sample_data, column_mappings=mappings)
    assert "Product_Title,Cost_USD" in mapped_csv
    assert "specs" not in mapped_csv


def test_background_worker_and_backoff():
    print("Testing background service worker routing and backoff...")
    worker = BackgroundServiceWorker()

    # Assertion 22: PING message returns PONG
    ok, res = worker.handle_message({"action": "PING"})
    assert ok is True
    assert res["status"] == "PONG"

    # Assertion 23: Batch queuing updates queue depth
    ok_q, res_q = worker.handle_message({
        "action": "QUEUE_EXPORT_BATCH",
        "payload": {"records": [{"id": 1}, {"id": 2}]}
    })
    assert ok_q is True
    assert res_q["queued_count"] == 2

    # Assertion 24: Exponential backoff delay on HTTP 429
    delay1 = worker.calculate_exponential_backoff(429)
    assert delay1 == 1.0
    delay2 = worker.calculate_exponential_backoff(429)
    assert delay2 == 2.0
    delay3 = worker.calculate_exponential_backoff(429)
    assert delay3 == 4.0

    # Assertion 25: Reset backoff delay on HTTP 200
    delay_reset = worker.calculate_exponential_backoff(200)
    assert delay_reset == 0.0
    assert worker.sync_backoff_seconds == 1.0


def main():
    print("=" * 70)
    print("STARTING E8 CHROME DATA EXPORTER DETERMINISTIC VERIFICATION SUITE")
    print("=" * 70)
    tracemalloc.start()

    test_models_and_enums()
    test_manifest_v3_compliance()
    test_csv_formula_injection_defense()
    test_html_table_parsing()
    test_rfc4180_csv_exporter()
    test_background_worker_and_backoff()

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
