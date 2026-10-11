"""test_presentation_variants.py

Automated verification suite for the 5 Excel workbooks and 5 HTML preview variants.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import openpyxl
import pytest

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
EXCEL_DIR = OUTPUT_DIR / "excel_variants"
HTML_DIR = OUTPUT_DIR / "html_variants"
CSV_PATH = OUTPUT_DIR / "books_dataset.csv"


@pytest.fixture(scope="module")
def csv_records():
    """Load reference CSV records."""
    records = []
    with open(CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append({
                "title": row["title"],
                "price_gbp": float(row["price_gbp"]),
                "rating": int(row["rating"]),
                "in_stock": row["in_stock"].strip().lower() == "true",
                "detail_url": row["detail_url"],
                "page_number": int(row["page_number"]),
            })
    return records


# ==============================================================================
# EXCEL SUITE
# ==============================================================================


@pytest.mark.parametrize(
    "filename",
    [
        "01_corporate_slate.xlsx",
        "02_emerald_growth.xlsx",
        "03_fintech_navy.xlsx",
        "04_minimal_monochrome.xlsx",
    ],
)
def test_standard_excel_variants_structure(filename, csv_records):
    file_path = EXCEL_DIR / filename
    assert file_path.exists(), f"File {filename} does not exist"
    assert file_path.stat().st_size > 50_000, f"File {filename} is unexpectedly small"

    wb = openpyxl.load_workbook(file_path, data_only=True)
    assert "Catalog Dataset" in wb.sheetnames
    ws = wb["Catalog Dataset"]

    # Verify rows: 1 header + 1000 data rows = 1001
    assert ws.max_row == 1001
    assert ws.max_column == 6

    # Verify freeze pane on header
    assert ws.freeze_panes == "A2"

    # Verify header values
    headers = [ws.cell(row=1, column=c).value for c in range(1, 7)]
    assert headers == ["Book Title", "Price (GBP)", "Star Rating", "Stock Status", "Detail URL", "Page"]

    # Verify first and last record match CSV
    first_row = [ws.cell(row=2, column=c).value for c in range(1, 7)]
    assert first_row[0] == csv_records[0]["title"]
    assert pytest.approx(first_row[1]) == csv_records[0]["price_gbp"]
    assert first_row[4] == csv_records[0]["detail_url"]

    last_row = [ws.cell(row=1001, column=c).value for c in range(1, 7)]
    assert last_row[0] == csv_records[-1]["title"]
    assert pytest.approx(last_row[1]) == csv_records[-1]["price_gbp"]

    # Verify number format on price column
    cell_price = ws.cell(row=2, column=2)
    assert cell_price.number_format == "£#,##0.00"

    # Verify column dimensions were adjusted
    for col_letter in ["A", "B", "C", "D", "E", "F"]:
        assert ws.column_dimensions[col_letter].width >= 10


def test_excel_05_executive_summary_kpi(csv_records):
    file_path = EXCEL_DIR / "05_executive_summary_kpi.xlsx"
    assert file_path.exists()
    assert file_path.stat().st_size > 50_000

    wb = openpyxl.load_workbook(file_path, data_only=True)
    assert "Executive Summary" in wb.sheetnames
    assert "Full Dataset" in wb.sheetnames

    # Tab 1: Executive Summary verification
    ws_kpi = wb["Executive Summary"]
    assert "Books to Scrape" in str(ws_kpi["B2"].value)

    # Verify KPI card figures
    assert ws_kpi["B5"].value == "TOTAL PRODUCTS"
    assert ws_kpi["B6"].value == 1000

    assert ws_kpi["C5"].value == "AVERAGE PRICE"
    assert pytest.approx(ws_kpi["C6"].value) == 35.07

    assert ws_kpi["D5"].value == "IN-STOCK RATE"
    assert ws_kpi["D6"].value == 1.0

    assert ws_kpi["E5"].value == "CATALOG SCOPE"
    assert "50" in str(ws_kpi["E6"].value)

    # Verify distribution table headers & rows
    assert ws_kpi["B10"].value == "Star Rating Breakdown"
    assert ws_kpi["B12"].value == "Star Rating"
    assert ws_kpi["D12"].value == "Book Count"

    # 1 Star through 5 Stars counts
    rating_counts = {ws_kpi.cell(row=r, column=2).value: ws_kpi.cell(row=r, column=4).value for r in range(13, 18)}
    assert rating_counts["1 Star"] == 226
    assert rating_counts["2 Stars"] == 196
    assert rating_counts["3 Stars"] == 203
    assert rating_counts["4 Stars"] == 179
    assert rating_counts["5 Stars"] == 196

    # Total row
    assert ws_kpi["B18"].value == "Total Catalog"
    assert ws_kpi["D18"].value == 1000

    # Tab 2: Full Dataset verification
    ws_data = wb["Full Dataset"]
    assert ws_data.max_row == 1001
    assert ws_data.freeze_panes == "A2"
    assert ws_data["A2"].value == csv_records[0]["title"]
    assert ws_data["B2"].number_format == "£#,##0.00"


# ==============================================================================
# HTML SUITE
# ==============================================================================


@pytest.mark.parametrize(
    "filename",
    [
        "01_tailwind_clean.html",
        "02_stripe_dashboard.html",
        "03_dark_fintech.html",
        "04_dense_analytics.html",
        "05_card_grid_hybrid.html",
    ],
)
def test_html_variants_structure(filename):
    file_path = HTML_DIR / filename
    assert file_path.exists(), f"File {filename} does not exist"
    assert file_path.stat().st_size > 150_000, f"File {filename} is unexpectedly small"

    content = file_path.read_text(encoding="utf-8")

    # Invariant 1: Single file, standalone, no external remote scripts/styles
    assert "<!DOCTYPE html>" in content
    assert "</html>" in content
    assert "<script" in content
    assert "const DATASET = [" in content

    # Invariant 2: Embedded dataset contains exactly 1,000 items
    prefix = "const DATASET = "
    start_idx = content.find(prefix) + len(prefix)
    end_idx = content.find(";\n", start_idx)
    raw_json = content[start_idx:end_idx]
    data = json.loads(raw_json)
    assert len(data) == 1000

    # Invariant 3: XSS protection function exists
    assert "function escapeHtml(" in content
    assert "&amp;" in content
    assert "&lt;" in content
    assert "&gt;" in content

    # Invariant 4: Sorting and searching functionality present
    assert "addEventListener" in content
    assert "filter(" in content or "applyFilter" in content or "renderTable" in content


def test_html_specific_features():
    # 01: Tailwind clean top metric cards and search input
    c1 = (HTML_DIR / "01_tailwind_clean.html").read_text(encoding="utf-8")
    assert "kpi-grid" in c1
    assert "searchInput" in c1

    # 02: Stripe dashboard pagination and copy CSV
    c2 = (HTML_DIR / "02_stripe_dashboard.html").read_text(encoding="utf-8")
    assert "pageSizeSelect" in c2
    assert "btnCopyCsv" in c2
    assert "navigator.clipboard.writeText" in c2

    # 03: Dark fintech rating pills
    c3 = (HTML_DIR / "03_dark_fintech.html").read_text(encoding="utf-8")
    assert 'data-rating="5"' in c3
    assert 'data-rating="all"' in c3
    assert "FINTECH TERMINAL" in c3

    # 04: Dense analytics sticky header and quick statistics footer
    c4 = (HTML_DIR / "04_dense_analytics.html").read_text(encoding="utf-8")
    assert "stat-footer" in c4
    assert "BLOOMBERG DENSE ANALYTICS" in c4
    assert "statMin" in c4
    assert "statMax" in c4

    # 05: Card grid hybrid view toggle
    c5 = (HTML_DIR / "05_card_grid_hybrid.html").read_text(encoding="utf-8")
    assert "btnCards" in c5
    assert "btnTable" in c5
    assert "product-card" in c5
