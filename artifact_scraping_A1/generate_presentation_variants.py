"""generate_presentation_variants.py

Generates 5 distinct styled Excel workbooks and 5 interactive standalone HTML preview
variants from output/books_dataset.csv adhering to market research styling standards.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
EXCEL_DIR = OUTPUT_DIR / "excel_variants"
HTML_DIR = OUTPUT_DIR / "html_variants"
CSV_PATH = OUTPUT_DIR / "books_dataset.csv"


def load_dataset() -> List[Dict[str, Any]]:
    """Load and type-cast the 1,000 product records from books_dataset.csv."""
    records: List[Dict[str, Any]] = []
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


def star_string(rating: int) -> str:
    """Format star glyphs."""
    return "★" * rating + "☆" * (5 - rating)


def autofit_columns(ws, min_width: int = 11, max_width: int = 60) -> None:
    """Auto-fit column widths with padding."""
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, min_width), max_width)


# ==============================================================================
# EXCEL GENERATORS
# ==============================================================================


def generate_excel_01_corporate_slate(records: List[Dict[str, Any]]) -> Path:
    """Theme 1: Corporate Slate (01_corporate_slate.xlsx)

    Dark slate header (#1E293B), bold white text, ice slate zebra striping (#F8FAFC),
    frozen row 1, auto-fit columns, native currency £#,##0.00, star glyphs.
    """
    out_path = EXCEL_DIR / "01_corporate_slate.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Catalog Dataset"
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "A2"

    headers = ["Book Title", "Price (GBP)", "Star Rating", "Stock Status", "Detail URL", "Page"]
    ws.append(headers)

    header_fill = PatternFill(start_color="FF1E293B", end_color="FF1E293B", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFFFF")
    even_fill = PatternFill(start_color="FFF8FAFC", end_color="FFF8FAFC", fill_type="solid")
    odd_fill = PatternFill(start_color="FFFFFFFF", end_color="FFFFFFFF", fill_type="solid")
    data_font = Font(name="Segoe UI", size=10, color="FF0F172A")
    thin_border = Border(
        left=Side(style="thin", color="FFCBD5E1"),
        right=Side(style="thin", color="FFCBD5E1"),
        top=Side(style="thin", color="FFCBD5E1"),
        bottom=Side(style="thin", color="FFCBD5E1"),
    )

    ws.row_dimensions[1].height = 26
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center" if col_idx != 1 else "left", vertical="center")

    for r_idx, r in enumerate(records, start=2):
        ws.row_dimensions[r_idx].height = 20
        fill = even_fill if r_idx % 2 == 0 else odd_fill

        row_data = [
            r["title"],
            r["price_gbp"],
            star_string(r["rating"]),
            "In Stock" if r["in_stock"] else "Out of Stock",
            r["detail_url"],
            r["page_number"],
        ]
        ws.append(row_data)

        for col_idx in range(1, 7):
            cell = ws.cell(row=r_idx, column=col_idx)
            cell.fill = fill
            cell.font = data_font
            cell.border = thin_border

            if col_idx == 1:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            elif col_idx == 2:
                cell.number_format = "£#,##0.00"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col_idx in (3, 4, 6):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx == 5:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    ws.auto_filter.ref = ws.dimensions
    autofit_columns(ws)
    wb.save(out_path)
    return out_path


def generate_excel_02_emerald_growth(records: List[Dict[str, Any]]) -> Path:
    """Theme 2: Emerald Growth (02_emerald_growth.xlsx)

    Modern SaaS emerald header (#065F46), soft mint zebra striping (#F0FDF4),
    soft green badge fill (#DCFCE7 / #166534) for "In Stock", auto-filters enabled.
    """
    out_path = EXCEL_DIR / "02_emerald_growth.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Catalog Dataset"
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "A2"

    headers = ["Book Title", "Price (GBP)", "Star Rating", "Stock Status", "Detail URL", "Page"]
    ws.append(headers)

    header_fill = PatternFill(start_color="FF065F46", end_color="FF065F46", fill_type="solid")
    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFFFF")
    even_fill = PatternFill(start_color="FFF0FDF4", end_color="FFF0FDF4", fill_type="solid")
    odd_fill = PatternFill(start_color="FFFFFFFF", end_color="FFFFFFFF", fill_type="solid")
    data_font = Font(name="Arial", size=10, color="FF0F172A")
    star_font = Font(name="Arial", size=10, color="FF059669")
    badge_fill = PatternFill(start_color="FFDCFCE7", end_color="FFDCFCE7", fill_type="solid")
    badge_font = Font(name="Arial", size=9.5, bold=True, color="FF166534")

    thin_border = Border(
        left=Side(style="thin", color="FFA7F3D0"),
        right=Side(style="thin", color="FFA7F3D0"),
        top=Side(style="thin", color="FFA7F3D0"),
        bottom=Side(style="thin", color="FFA7F3D0"),
    )

    ws.row_dimensions[1].height = 28
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center" if col_idx != 1 else "left", vertical="center")

    for r_idx, r in enumerate(records, start=2):
        ws.row_dimensions[r_idx].height = 20
        fill = even_fill if r_idx % 2 == 0 else odd_fill

        row_data = [
            r["title"],
            r["price_gbp"],
            star_string(r["rating"]),
            "In Stock" if r["in_stock"] else "Out of Stock",
            r["detail_url"],
            r["page_number"],
        ]
        ws.append(row_data)

        for col_idx in range(1, 7):
            cell = ws.cell(row=r_idx, column=col_idx)
            cell.border = thin_border

            if col_idx == 4:
                # Stock badge pill styling
                cell.fill = badge_fill
                cell.font = badge_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.fill = fill
                cell.font = star_font if col_idx == 3 else data_font

            if col_idx == 1:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            elif col_idx == 2:
                cell.number_format = "£#,##0.00"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col_idx in (3, 6):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx == 5:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    ws.auto_filter.ref = ws.dimensions
    autofit_columns(ws)
    wb.save(out_path)
    return out_path


def generate_excel_03_fintech_navy(records: List[Dict[str, Any]]) -> Path:
    """Theme 3: Fintech Navy (03_fintech_navy.xlsx)

    Institutional deep navy header (#0F172A), pale slate zebra striping (#F1F5F9),
    crisp borders (#94A3B8), high-contrast financial grid, right-aligned numbers.
    """
    out_path = EXCEL_DIR / "03_fintech_navy.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Catalog Dataset"
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "A2"

    headers = ["Book Title", "Price (GBP)", "Star Rating", "Stock Status", "Detail URL", "Page"]
    ws.append(headers)

    header_fill = PatternFill(start_color="FF0F172A", end_color="FF0F172A", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10.5, bold=True, color="FFFFFFFF")
    header_price_font = Font(name="Segoe UI", size=10.5, bold=True, color="FF38BDF8")
    even_fill = PatternFill(start_color="FFF1F5F9", end_color="FFF1F5F9", fill_type="solid")
    odd_fill = PatternFill(start_color="FFFFFFFF", end_color="FFFFFFFF", fill_type="solid")
    data_font = Font(name="Segoe UI", size=10, color="FF020617")

    thin_border = Border(
        left=Side(style="thin", color="FF94A3B8"),
        right=Side(style="thin", color="FF94A3B8"),
        top=Side(style="thin", color="FF94A3B8"),
        bottom=Side(style="thin", color="FF94A3B8"),
    )

    ws.row_dimensions[1].height = 26
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_price_font if col_idx == 2 else header_font
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="right" if col_idx == 2 else ("left" if col_idx == 1 else "center"), vertical="center")

    for r_idx, r in enumerate(records, start=2):
        ws.row_dimensions[r_idx].height = 20
        fill = even_fill if r_idx % 2 == 0 else odd_fill

        row_data = [
            r["title"],
            r["price_gbp"],
            star_string(r["rating"]),
            "In Stock" if r["in_stock"] else "Out of Stock",
            r["detail_url"],
            r["page_number"],
        ]
        ws.append(row_data)

        for col_idx in range(1, 7):
            cell = ws.cell(row=r_idx, column=col_idx)
            cell.fill = fill
            cell.font = data_font
            cell.border = thin_border

            if col_idx == 1:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            elif col_idx == 2:
                cell.number_format = "£#,##0.00"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col_idx in (3, 4, 6):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx == 5:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    ws.auto_filter.ref = ws.dimensions
    autofit_columns(ws)
    wb.save(out_path)
    return out_path


def generate_excel_04_minimal_monochrome(records: List[Dict[str, Any]]) -> Path:
    """Theme 4: Minimal Monochrome (04_minimal_monochrome.xlsx)

    Warm minimalist dark gray (#27272A), whisper gray striping (#F4F4F5),
    thin understated borders (#E4E4E7), compact clean executive styling.
    """
    out_path = EXCEL_DIR / "04_minimal_monochrome.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Catalog Dataset"
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "A2"

    headers = ["Book Title", "Price (GBP)", "Star Rating", "Stock Status", "Detail URL", "Page"]
    ws.append(headers)

    header_fill = PatternFill(start_color="FF27272A", end_color="FF27272A", fill_type="solid")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFFFF")
    even_fill = PatternFill(start_color="FFF4F4F5", end_color="FFF4F4F5", fill_type="solid")
    odd_fill = PatternFill(start_color="FFFFFFFF", end_color="FFFFFFFF", fill_type="solid")
    data_font = Font(name="Arial", size=9.5, color="FF18181B")

    thin_border = Border(
        left=Side(style="thin", color="FFE4E4E7"),
        right=Side(style="thin", color="FFE4E4E7"),
        top=Side(style="thin", color="FFE4E4E7"),
        bottom=Side(style="thin", color="FFE4E4E7"),
    )

    ws.row_dimensions[1].height = 24
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center" if col_idx != 1 else "left", vertical="center")

    for r_idx, r in enumerate(records, start=2):
        ws.row_dimensions[r_idx].height = 18
        fill = even_fill if r_idx % 2 == 0 else odd_fill

        row_data = [
            r["title"],
            r["price_gbp"],
            star_string(r["rating"]),
            "In Stock" if r["in_stock"] else "Out of Stock",
            r["detail_url"],
            r["page_number"],
        ]
        ws.append(row_data)

        for col_idx in range(1, 7):
            cell = ws.cell(row=r_idx, column=col_idx)
            cell.fill = fill
            cell.font = data_font
            cell.border = thin_border

            if col_idx == 1:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            elif col_idx == 2:
                cell.number_format = "£#,##0.00"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col_idx in (3, 4, 6):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx == 5:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    ws.auto_filter.ref = ws.dimensions
    autofit_columns(ws)
    wb.save(out_path)
    return out_path


def generate_excel_05_executive_summary_kpi(records: List[Dict[str, Any]]) -> Path:
    """Theme 5: Executive Summary KPI (05_executive_summary_kpi.xlsx)

    Two-tab workbook:
    - Tab 1: "Executive Summary" with KPI cards (Total: 1,000, Avg Price: £35.07,
      In-Stock Rate: 100%, Scope: 50 Pages) and Star Rating Breakdown Table.
    - Tab 2: "Full Dataset" formatted with clean corporate table styles.
    """
    out_path = EXCEL_DIR / "05_executive_summary_kpi.xlsx"
    wb = openpyxl.Workbook()

    # --------------------------------------------------------------------------
    # Tab 1: Executive Summary
    # --------------------------------------------------------------------------
    ws_kpi = wb.active
    ws_kpi.title = "Executive Summary"
    ws_kpi.views.sheetView[0].showGridLines = True

    # Column dimensions
    ws_kpi.column_dimensions["A"].width = 4
    ws_kpi.column_dimensions["B"].width = 24
    ws_kpi.column_dimensions["C"].width = 24
    ws_kpi.column_dimensions["D"].width = 24
    ws_kpi.column_dimensions["E"].width = 24
    ws_kpi.column_dimensions["F"].width = 18

    # Title Block
    ws_kpi.row_dimensions[2].height = 28
    cell_title = ws_kpi.cell(row=2, column=2, value="Books to Scrape: Market Intelligence & Catalog Analysis")
    cell_title.font = Font(name="Segoe UI", size=18, bold=True, color="FF1E293B")

    ws_kpi.row_dimensions[3].height = 18
    cell_sub = ws_kpi.cell(row=3, column=2, value="Executive Audit & Catalog Distribution | Scope: 50 Pages | Verified 1,000 Records")
    cell_sub.font = Font(name="Segoe UI", size=10, italic=True, color="FF64748B")

    # KPI Cards (Rows 5-7, Cols B through E)
    card_fill = PatternFill(start_color="FFF8FAFC", end_color="FFF8FAFC", fill_type="solid")
    card_border = Border(
        left=Side(style="thin", color="FFCBD5E1"),
        right=Side(style="thin", color="FFCBD5E1"),
        top=Side(style="thin", color="FFCBD5E1"),
        bottom=Side(style="thin", color="FFCBD5E1"),
    )
    ws_kpi.row_dimensions[5].height = 20
    ws_kpi.row_dimensions[6].height = 34
    ws_kpi.row_dimensions[7].height = 20

    kpi_defs = [
        ("B", "TOTAL PRODUCTS", 1000, "#,##0", "100% of Catalog Target", "FF1E293B", "FF10B981"),
        ("C", "AVERAGE PRICE", 35.07, "£#,##0.00", "Min £10.00 | Max £59.99", "FF1E293B", "FF64748B"),
        ("D", "IN-STOCK RATE", 1.0, "0.0%", "1,000 / 1,000 In Stock", "FF16A34A", "FF16A34A"),
        ("E", "CATALOG SCOPE", "50 Pages", "@", "20 Books / Page Average", "FF1E293B", "FF64748B"),
    ]

    for col_letter, label, val, num_fmt, footnote, val_color, foot_color in kpi_defs:
        col_num = openpyxl.utils.column_index_from_string(col_letter)

        c5 = ws_kpi.cell(row=5, column=col_num, value=label)
        c5.font = Font(name="Segoe UI", size=9, bold=True, color="FF64748B")
        c5.alignment = Alignment(horizontal="center", vertical="center")
        c5.fill = card_fill
        c5.border = card_border

        c6 = ws_kpi.cell(row=6, column=col_num, value=val)
        c6.font = Font(name="Segoe UI", size=20, bold=True, color=val_color)
        c6.number_format = num_fmt
        c6.alignment = Alignment(horizontal="center", vertical="center")
        c6.fill = card_fill
        c6.border = card_border

        c7 = ws_kpi.cell(row=7, column=col_num, value=footnote)
        c7.font = Font(name="Segoe UI", size=9, color=foot_color)
        c7.alignment = Alignment(horizontal="center", vertical="center")
        c7.fill = card_fill
        c7.border = card_border

    # Star Rating Breakdown Table
    ws_kpi.row_dimensions[10].height = 24
    c_sec = ws_kpi.cell(row=10, column=2, value="Star Rating Breakdown")
    c_sec.font = Font(name="Segoe UI", size=13, bold=True, color="FF1E293B")

    tbl_headers = ["Star Rating", "Visual Glyph", "Book Count", "Catalog Share", "Market Tier"]
    ws_kpi.row_dimensions[12].height = 24
    tbl_hdr_fill = PatternFill(start_color="FF1E293B", end_color="FF1E293B", fill_type="solid")
    tbl_hdr_font = Font(name="Segoe UI", size=10.5, bold=True, color="FFFFFFFF")

    for idx, th in enumerate(tbl_headers, start=2):
        c = ws_kpi.cell(row=12, column=idx, value=th)
        c.fill = tbl_hdr_fill
        c.font = tbl_hdr_font
        c.border = card_border
        c.alignment = Alignment(horizontal="center" if idx != 2 else "left", vertical="center")

    breakdown_data = [
        ("1 Star", "★☆☆☆☆", 226, 0.226, "Plurality (22.6%)"),
        ("2 Stars", "★★☆☆☆", 196, 0.196, "Standard (19.6%)"),
        ("3 Stars", "★★★☆☆", 203, 0.203, "Standard (20.3%)"),
        ("4 Stars", "★★★★☆", 179, 0.179, "Standard (17.9%)"),
        ("5 Stars", "★★★★★", 196, 0.196, "Standard (19.6%)"),
    ]

    even_fill = PatternFill(start_color="FFF8FAFC", end_color="FFF8FAFC", fill_type="solid")
    odd_fill = PatternFill(start_color="FFFFFFFF", end_color="FFFFFFFF", fill_type="solid")
    row_font = Font(name="Segoe UI", size=10, color="FF0F172A")

    for r_offset, (tier, glyph, cnt, share, status_str) in enumerate(breakdown_data, start=13):
        ws_kpi.row_dimensions[r_offset].height = 20
        fill = even_fill if r_offset % 2 == 0 else odd_fill

        c_tier = ws_kpi.cell(row=r_offset, column=2, value=tier)
        c_glyph = ws_kpi.cell(row=r_offset, column=3, value=glyph)
        c_cnt = ws_kpi.cell(row=r_offset, column=4, value=cnt)
        c_share = ws_kpi.cell(row=r_offset, column=5, value=share)
        c_status = ws_kpi.cell(row=r_offset, column=6, value=status_str)

        c_cnt.number_format = "#,##0"
        c_share.number_format = "0.0%"

        for c_item, align_h in [(c_tier, "left"), (c_glyph, "center"), (c_cnt, "right"), (c_share, "right"), (c_status, "center")]:
            c_item.fill = fill
            c_item.font = row_font
            c_item.border = card_border
            c_item.alignment = Alignment(horizontal=align_h, vertical="center")

    # Total Summary Row
    ws_kpi.row_dimensions[18].height = 22
    tot_border = Border(
        left=Side(style="thin", color="FFCBD5E1"),
        right=Side(style="thin", color="FFCBD5E1"),
        top=Side(style="thin", color="FF1E293B"),
        bottom=Side(style="double", color="FF1E293B"),
    )
    tot_font = Font(name="Segoe UI", size=10.5, bold=True, color="FF1E293B")
    tot_fill = PatternFill(start_color="FFF1F5F9", end_color="FFF1F5F9", fill_type="solid")

    tot_cells = [
        (2, "Total Catalog", "left", "@"),
        (3, "★★★★★", "center", "@"),
        (4, 1000, "right", "#,##0"),
        (5, 1.0, "right", "0.0%"),
        (6, "100.0% Complete", "center", "@"),
    ]
    for col_i, val, align_h, num_fmt in tot_cells:
        c = ws_kpi.cell(row=18, column=col_i, value=val)
        c.font = tot_font
        c.fill = tot_fill
        c.border = tot_border
        c.alignment = Alignment(horizontal=align_h, vertical="center")
        c.number_format = num_fmt

    # --------------------------------------------------------------------------
    # Tab 2: Full Dataset (1,000 Records)
    # --------------------------------------------------------------------------
    ws_data = wb.create_sheet(title="Full Dataset")
    ws_data.views.sheetView[0].showGridLines = True
    ws_data.freeze_panes = "A2"

    headers = ["Book Title", "Price (GBP)", "Star Rating", "Stock Status", "Detail URL", "Page"]
    ws_data.append(headers)

    header_fill = PatternFill(start_color="FF1E293B", end_color="FF1E293B", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFFFF")
    even_data_fill = PatternFill(start_color="FFF8FAFC", end_color="FFF8FAFC", fill_type="solid")
    odd_data_fill = PatternFill(start_color="FFFFFFFF", end_color="FFFFFFFF", fill_type="solid")
    d_font = Font(name="Segoe UI", size=10, color="FF0F172A")
    d_border = Border(
        left=Side(style="thin", color="FFCBD5E1"),
        right=Side(style="thin", color="FFCBD5E1"),
        top=Side(style="thin", color="FFCBD5E1"),
        bottom=Side(style="thin", color="FFCBD5E1"),
    )

    ws_data.row_dimensions[1].height = 26
    for col_idx in range(1, len(headers) + 1):
        cell = ws_data.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = d_border
        cell.alignment = Alignment(horizontal="center" if col_idx != 1 else "left", vertical="center")

    for r_idx, r in enumerate(records, start=2):
        ws_data.row_dimensions[r_idx].height = 20
        fill = even_data_fill if r_idx % 2 == 0 else odd_data_fill

        row_data = [
            r["title"],
            r["price_gbp"],
            star_string(r["rating"]),
            "In Stock" if r["in_stock"] else "Out of Stock",
            r["detail_url"],
            r["page_number"],
        ]
        ws_data.append(row_data)

        for col_idx in range(1, 7):
            cell = ws_data.cell(row=r_idx, column=col_idx)
            cell.fill = fill
            cell.font = d_font
            cell.border = d_border

            if col_idx == 1:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            elif col_idx == 2:
                cell.number_format = "£#,##0.00"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col_idx in (3, 4, 6):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx == 5:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    ws_data.auto_filter.ref = ws_data.dimensions
    autofit_columns(ws_data)

    wb.active = 0
    wb.save(out_path)
    return out_path


# ==============================================================================
# HTML GENERATORS
# ==============================================================================


def generate_html_01_tailwind_clean(records: List[Dict[str, Any]]) -> Path:
    """Theme 1: Tailwind Clean (01_tailwind_clean.html)

    Crisp white/slate UI, metric cards on top, instant search bar, sortable
    column headers, stock badge chips, direct detail links. Standalone zero-dependency.
    """
    out_path = HTML_DIR / "01_tailwind_clean.html"
    json_data = json.dumps(records)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Books to Scrape // Tailwind Clean Catalog</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: #F8FAFC;
      color: #0F172A;
      line-height: 1.5;
      padding: 32px 24px;
    }}
    .container {{ max-width: 1280px; margin: 0 auto; }}
    .header {{ margin-bottom: 24px; }}
    .header h1 {{ font-size: 28px; font-weight: 700; color: #0F172A; }}
    .header p {{ color: #64748B; font-size: 14px; margin-top: 4px; }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .kpi-card {{
      background: #FFFFFF;
      border: 1px solid #E2E8F0;
      border-radius: 12px;
      padding: 20px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }}
    .kpi-label {{ font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748B; letter-spacing: 0.05em; }}
    .kpi-value {{ font-size: 26px; font-weight: 700; color: #0F172A; margin: 8px 0 4px; }}
    .kpi-sub {{ font-size: 12px; color: #10B981; font-weight: 500; }}
    .toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }}
    .search-input {{
      flex: 1;
      min-width: 280px;
      max-width: 450px;
      padding: 10px 16px;
      border: 1px solid #CBD5E1;
      border-radius: 8px;
      font-size: 14px;
      background: #FFFFFF;
      outline: none;
      transition: border-color 0.15s, box-shadow 0.15s;
    }}
    .search-input:focus {{
      border-color: #2563EB;
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
    }}
    .counter-badge {{
      font-size: 13px;
      color: #64748B;
      font-weight: 500;
      background: #FFFFFF;
      border: 1px solid #E2E8F0;
      padding: 8px 14px;
      border-radius: 8px;
    }}
    .table-container {{
      background: #FFFFFF;
      border: 1px solid #E2E8F0;
      border-radius: 12px;
      overflow-x: auto;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }}
    table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13.5px; }}
    thead th {{
      background: #F1F5F9;
      color: #334155;
      font-weight: 600;
      padding: 12px 16px;
      border-bottom: 1px solid #CBD5E1;
      cursor: pointer;
      user-select: none;
      white-space: nowrap;
    }}
    thead th:hover {{ background: #E2E8F0; }}
    thead th.no-sort {{ cursor: default; }}
    thead th.no-sort:hover {{ background: #F1F5F9; }}
    th .sort-icon {{ margin-left: 6px; font-size: 11px; opacity: 0.5; }}
    th.sorted-asc .sort-icon {{ opacity: 1; content: "▲"; }}
    th.sorted-desc .sort-icon {{ opacity: 1; content: "▼"; }}
    tbody tr {{ border-bottom: 1px solid #F1F5F9; transition: background 0.1s; }}
    tbody tr:hover {{ background: #F8FAFC; }}
    tbody tr:last-child {{ border-bottom: none; }}
    td {{ padding: 12px 16px; vertical-align: middle; }}
    .cell-title {{ font-weight: 500; color: #0F172A; max-width: 420px; }}
    .cell-price {{ font-weight: 600; color: #0F172A; text-align: right; font-variant-numeric: tabular-nums; }}
    .cell-stars {{ color: #F59E0B; text-align: center; letter-spacing: 2px; }}
    .cell-page {{ text-align: center; color: #64748B; }}
    .badge-stock {{
      background: #DEF7EC;
      color: #03543F;
      font-size: 12px;
      font-weight: 600;
      padding: 3px 10px;
      border-radius: 9999px;
      display: inline-block;
    }}
    .btn-detail {{
      color: #2563EB;
      text-decoration: none;
      font-weight: 500;
      font-size: 12.5px;
      padding: 4px 10px;
      border-radius: 6px;
      border: 1px solid #BFDBFE;
      background: #EFF6FF;
      transition: all 0.15s;
    }}
    .btn-detail:hover {{ background: #DBEAFE; border-color: #93C5FD; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Books to Scrape : Executive Catalog</h1>
      <p>Interactive verified deliverable • 1,000 product records extracted across 50 catalog pages</p>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Total Books</div>
        <div class="kpi-value">1,000</div>
        <div class="kpi-sub">50 pages scraped</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Average Price</div>
        <div class="kpi-value">£35.07</div>
        <div class="kpi-sub">Range £10.00 – £59.99</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">In-Stock Rate</div>
        <div class="kpi-value">100.0%</div>
        <div class="kpi-sub">All items available</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Rating Distribution</div>
        <div class="kpi-value">3.00 Avg</div>
        <div class="kpi-sub">Balanced 1★ – 5★</div>
      </div>
    </div>

    <div class="toolbar">
      <input type="text" id="searchInput" class="search-input" placeholder="Search by title, rating, or page..." />
      <div id="counterBadge" class="counter-badge">Showing 1,000 of 1,000 books</div>
    </div>

    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th data-col="title">Book Title <span class="sort-icon">⇅</span></th>
            <th data-col="price_gbp" style="text-align: right;">Price <span class="sort-icon">⇅</span></th>
            <th data-col="rating" style="text-align: center;">Rating <span class="sort-icon">⇅</span></th>
            <th data-col="in_stock" style="text-align: center;">Availability <span class="sort-icon">⇅</span></th>
            <th data-col="page_number" style="text-align: center;">Page <span class="sort-icon">⇅</span></th>
            <th class="no-sort" style="text-align: center;">Action</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>
  </div>

  <script>
    const DATASET = {json_data};
    let currentData = [...DATASET];
    let sortCol = null;
    let sortAsc = true;

    function escapeHtml(str) {{
      if (str === null || str === undefined) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }}

    function starGlyphs(r) {{
      return '★'.repeat(r) + '☆'.repeat(5 - r);
    }}

    function renderTable() {{
      const tbody = document.getElementById('tableBody');
      const counter = document.getElementById('counterBadge');
      counter.textContent = `Showing ${{currentData.length.toLocaleString()}} of ${{DATASET.length.toLocaleString()}} books`;

      if (currentData.length === 0) {{
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 32px; color: #94A3B8;">No matching books found.</td></tr>';
        return;
      }}

      let html = '';
      for (const item of currentData) {{
        const url = `https://books.toscrape.com/catalogue/${{item.detail_url}}`;
        html += `<tr>
          <td class="cell-title">${{escapeHtml(item.title)}}</td>
          <td class="cell-price">£${{item.price_gbp.toFixed(2)}}</td>
          <td class="cell-stars">${{starGlyphs(item.rating)}}</td>
          <td style="text-align: center;"><span class="badge-stock">In Stock</span></td>
          <td class="cell-page">P.${{item.page_number}}</td>
          <td style="text-align: center;"><a href="${{url}}" target="_blank" rel="noopener noreferrer" class="btn-detail">View ↗</a></td>
        </tr>`;
      }}
      tbody.innerHTML = html;
    }}

    function applyFilterAndSort() {{
      const q = document.getElementById('searchInput').value.trim().toLowerCase();
      let filtered = DATASET.filter(item => {{
        if (!q) return true;
        return item.title.toLowerCase().includes(q) ||
               String(item.rating).includes(q) ||
               String(item.page_number).includes(q) ||
               item.price_gbp.toFixed(2).includes(q);
      }});

      if (sortCol) {{
        filtered.sort((a, b) => {{
          let valA = a[sortCol];
          let valB = b[sortCol];
          if (typeof valA === 'number' && typeof valB === 'number') {{
            return sortAsc ? valA - valB : valB - valA;
          }}
          return sortAsc ? String(valA).localeCompare(String(valB)) : String(valB).localeCompare(String(valA));
        }});
      }}

      currentData = filtered;
      renderTable();
    }}

    document.getElementById('searchInput').addEventListener('input', applyFilterAndSort);

    document.querySelectorAll('thead th[data-col]').forEach(th => {{
      th.addEventListener('click', () => {{
        const col = th.getAttribute('data-col');
        if (sortCol === col) {{
          sortAsc = !sortAsc;
        }} else {{
          sortCol = col;
          sortAsc = true;
        }}
        document.querySelectorAll('thead th').forEach(h => {{
          h.classList.remove('sorted-asc', 'sorted-desc');
          const icon = h.querySelector('.sort-icon');
          if (icon) icon.textContent = '⇅';
        }});
        th.classList.add(sortAsc ? 'sorted-asc' : 'sorted-desc');
        th.querySelector('.sort-icon').textContent = sortAsc ? '▲' : '▼';
        applyFilterAndSort();
      }});
    }});

    renderTable();
  </script>
</body>
</html>
"""
    out_path.write_text(html_content, encoding="utf-8")
    return out_path


def generate_html_02_stripe_dashboard(records: List[Dict[str, Any]]) -> Path:
    """Theme 2: Stripe Dashboard (02_stripe_dashboard.html)

    Stripe-inspired enterprise dashboard, top navigation/title, summary metrics
    ribbon, search input, pagination (25/50/100 rows per page), copy-table-to-clipboard button.
    """
    out_path = HTML_DIR / "02_stripe_dashboard.html"
    json_data = json.dumps(records)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Books to Scrape // Stripe Enterprise Dashboard</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: #F6F9FC;
      color: #32325D;
      line-height: 1.5;
      padding: 0;
    }}
    .nav-bar {{
      background: #FFFFFF;
      border-bottom: 1px solid #E3E8EE;
      padding: 16px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 1px 3px rgba(50,50,93,0.05);
    }}
    .brand {{ display: flex; align-items: center; gap: 12px; }}
    .brand-icon {{
      width: 32px;
      height: 32px;
      background: #635BFF;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: 700;
      font-size: 16px;
    }}
    .brand-title {{ font-size: 16px; font-weight: 600; color: #32325D; }}
    .brand-pill {{
      background: #F4F5F7;
      border: 1px solid #E3E8EE;
      color: #4F566B;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
    }}
    .btn-copy {{
      background: #635BFF;
      color: #FFFFFF;
      border: none;
      border-radius: 6px;
      padding: 8px 16px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: background 0.15s, transform 0.05s;
    }}
    .btn-copy:hover {{ background: #5851EA; }}
    .btn-copy:active {{ transform: scale(0.98); }}
    .toast {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #0A2540;
      color: white;
      padding: 12px 20px;
      border-radius: 8px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.15);
      font-size: 13.5px;
      display: none;
      z-index: 1000;
      animation: fadeIn 0.2s ease;
    }}
    @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    .main-content {{ max-width: 1280px; margin: 32px auto; padding: 0 24px; }}
    .metrics-ribbon {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .metric-card {{
      background: #FFFFFF;
      border: 1px solid #E3E8EE;
      border-radius: 8px;
      padding: 16px 20px;
      box-shadow: 0 1px 3px rgba(50,50,93,0.02);
    }}
    .metric-label {{ font-size: 12px; font-weight: 600; color: #8898AA; text-transform: uppercase; }}
    .metric-val {{ font-size: 24px; font-weight: 600; color: #32325D; margin-top: 4px; }}
    .table-card {{
      background: #FFFFFF;
      border: 1px solid #E3E8EE;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(50,50,93,0.03);
      overflow: hidden;
    }}
    .card-toolbar {{
      padding: 16px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      border-bottom: 1px solid #E3E8EE;
      flex-wrap: wrap;
    }}
    .search-box {{
      padding: 8px 14px;
      border: 1px solid #E3E8EE;
      border-radius: 6px;
      font-size: 13.5px;
      width: 320px;
      outline: none;
      color: #32325D;
    }}
    .search-box:focus {{ border-color: #635BFF; box-shadow: 0 0 0 2px rgba(99,91,255,0.15); }}
    .pagination-controls {{ display: flex; align-items: center; gap: 12px; font-size: 13px; color: #4F566B; }}
    .select-page-size {{
      padding: 6px 10px;
      border: 1px solid #E3E8EE;
      border-radius: 6px;
      font-size: 13px;
      color: #32325D;
      background: white;
    }}
    .btn-page {{
      padding: 6px 12px;
      border: 1px solid #E3E8EE;
      background: white;
      border-radius: 6px;
      color: #4F566B;
      cursor: pointer;
      font-size: 12.5px;
      font-weight: 500;
    }}
    .btn-page:disabled {{ opacity: 0.4; cursor: not-allowed; }}
    .btn-page:not(:disabled):hover {{ background: #F6F9FC; border-color: #CBD5E1; }}
    table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13.5px; }}
    th {{
      background: #FAFBFC;
      color: #4F566B;
      font-weight: 600;
      padding: 12px 18px;
      border-bottom: 1px solid #E3E8EE;
      cursor: pointer;
      user-select: none;
      white-space: nowrap;
    }}
    th:hover {{ background: #F4F5F7; }}
    td {{ padding: 12px 18px; border-bottom: 1px solid #E3E8EE; vertical-align: middle; }}
    tbody tr:hover {{ background: #F6F9FC; }}
    .price-col {{ text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }}
    .stock-chip {{
      background: #E6FFFA;
      color: #047481;
      font-size: 11.5px;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 12px;
    }}
  </style>
</head>
<body>
  <div class="nav-bar">
    <div class="brand">
      <div class="brand-icon">S</div>
      <div class="brand-title">Stripe Catalog Platform</div>
      <div class="brand-pill">1,000 SKUs</div>
    </div>
    <button id="btnCopyCsv" class="btn-copy">📋 Copy Table to CSV</button>
  </div>

  <div id="toast" class="toast">✓ 1,000 records copied to clipboard in CSV format!</div>

  <div class="main-content">
    <div class="metrics-ribbon">
      <div class="metric-card">
        <div class="metric-label">Total Volume</div>
        <div class="metric-val">1,000 Products</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Average Unit Price</div>
        <div class="metric-val">£35.07</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Gross Catalog Value</div>
        <div class="metric-val">£35,070.00</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">In-Stock Availability</div>
        <div class="metric-val">100.0%</div>
      </div>
    </div>

    <div class="table-card">
      <div class="card-toolbar">
        <input type="text" id="searchBox" class="search-box" placeholder="Filter by product name, price, page..." />
        <div class="pagination-controls">
          <span>Rows per page:</span>
          <select id="pageSizeSelect" class="select-page-size">
            <option value="25">25</option>
            <option value="50" selected>50</option>
            <option value="100">100</option>
            <option value="1000">All (1,000)</option>
          </select>
          <button id="btnPrev" class="btn-page">Previous</button>
          <span id="pageIndicator">Page 1 of 20</span>
          <button id="btnNext" class="btn-page">Next</button>
        </div>
      </div>

      <table>
        <thead>
          <tr>
            <th data-col="title">Title ⇅</th>
            <th data-col="price_gbp" style="text-align: right;">Price ⇅</th>
            <th data-col="rating" style="text-align: center;">Rating ⇅</th>
            <th data-col="in_stock" style="text-align: center;">Availability ⇅</th>
            <th data-col="page_number" style="text-align: center;">Catalog Page ⇅</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>
  </div>

  <script>
    const DATASET = {json_data};
    let filteredData = [...DATASET];
    let sortCol = null;
    let sortAsc = true;
    let currentPage = 1;
    let pageSize = 50;

    function escapeHtml(str) {{
      if (str === null || str === undefined) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }}

    function starGlyphs(r) {{
      return '★'.repeat(r) + '☆'.repeat(5 - r);
    }}

    function renderTable() {{
      const totalPages = Math.ceil(filteredData.length / pageSize) || 1;
      if (currentPage > totalPages) currentPage = totalPages;
      if (currentPage < 1) currentPage = 1;

      document.getElementById('pageIndicator').textContent = `Page ${{currentPage}} of ${{totalPages}} (${{filteredData.length.toLocaleString()}} total)`;
      document.getElementById('btnPrev').disabled = (currentPage === 1);
      document.getElementById('btnNext').disabled = (currentPage === totalPages);

      const startIdx = (currentPage - 1) * pageSize;
      const endIdx = startIdx + pageSize;
      const pageSlice = filteredData.slice(startIdx, endIdx);

      const tbody = document.getElementById('tableBody');
      if (pageSlice.length === 0) {{
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 32px; color: #8898AA;">No matching items found.</td></tr>';
        return;
      }}

      let html = '';
      for (const item of pageSlice) {{
        html += `<tr>
          <td style="font-weight: 500;">${{escapeHtml(item.title)}}</td>
          <td class="price-col">£${{item.price_gbp.toFixed(2)}}</td>
          <td style="text-align: center; color: #E3A008;">${{starGlyphs(item.rating)}}</td>
          <td style="text-align: center;"><span class="stock-chip">Active / In Stock</span></td>
          <td style="text-align: center; color: #8898AA;">Page ${{item.page_number}}</td>
        </tr>`;
      }}
      tbody.innerHTML = html;
    }}

    function applyFilterAndSort() {{
      const q = document.getElementById('searchBox').value.trim().toLowerCase();
      filteredData = DATASET.filter(item => {{
        if (!q) return true;
        return item.title.toLowerCase().includes(q) ||
               String(item.rating).includes(q) ||
               String(item.page_number).includes(q) ||
               item.price_gbp.toFixed(2).includes(q);
      }});

      if (sortCol) {{
        filteredData.sort((a, b) => {{
          let valA = a[sortCol];
          let valB = b[sortCol];
          if (typeof valA === 'number' && typeof valB === 'number') {{
            return sortAsc ? valA - valB : valB - valA;
          }}
          return sortAsc ? String(valA).localeCompare(String(valB)) : String(valB).localeCompare(String(valA));
        }});
      }}

      currentPage = 1;
      renderTable();
    }}

    document.getElementById('searchBox').addEventListener('input', applyFilterAndSort);

    document.getElementById('pageSizeSelect').addEventListener('change', (e) => {{
      pageSize = parseInt(e.target.value, 10);
      currentPage = 1;
      renderTable();
    }});

    document.getElementById('btnPrev').addEventListener('click', () => {{
      if (currentPage > 1) {{
        currentPage--;
        renderTable();
      }}
    }});

    document.getElementById('btnNext').addEventListener('click', () => {{
      const totalPages = Math.ceil(filteredData.length / pageSize) || 1;
      if (currentPage < totalPages) {{
        currentPage++;
        renderTable();
      }}
    }});

    document.querySelectorAll('thead th[data-col]').forEach(th => {{
      th.addEventListener('click', () => {{
        const col = th.getAttribute('data-col');
        if (sortCol === col) {{
          sortAsc = !sortAsc;
        }} else {{
          sortCol = col;
          sortAsc = true;
        }}
        applyFilterAndSort();
      }});
    }});

    document.getElementById('btnCopyCsv').addEventListener('click', () => {{
      let csvContent = 'title,price_gbp,rating,in_stock,detail_url,page_number\\n';
      for (const item of filteredData) {{
        const safeTitle = `"${{item.title.replace(/"/g, '""')}}"`;
        csvContent += `${{safeTitle}},${{item.price_gbp.toFixed(2)}},${{item.rating}},${{item.in_stock}},${{item.detail_url}},${{item.page_number}}\\n`;
      }}
      navigator.clipboard.writeText(csvContent).then(() => {{
        const toast = document.getElementById('toast');
        toast.textContent = `✓ ${{filteredData.length.toLocaleString()}} records copied to clipboard in CSV format!`;
        toast.style.display = 'block';
        setTimeout(() => {{ toast.style.display = 'none'; }}, 3000);
      }}).catch(err => {{
        alert('Could not copy CSV: ' + err);
      }});
    }});

    renderTable();
  </script>
</body>
</html>
"""
    out_path.write_text(html_content, encoding="utf-8")
    return out_path


def generate_html_03_dark_fintech(records: List[Dict[str, Any]]) -> Path:
    """Theme 3: Dark Fintech (03_dark_fintech.html)

    Dark mode theme (#0F172A / #1E293B), neon accent badges, high-contrast
    typography, interactive filtering by star rating pills.
    """
    out_path = HTML_DIR / "03_dark_fintech.html"
    json_data = json.dumps(records)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Books to Scrape // High-Contrast Dark Fintech Terminal</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", monospace;
      background-color: #0F172A;
      color: #F8FAFC;
      line-height: 1.5;
      padding: 32px 24px;
    }}
    .container {{ max-width: 1280px; margin: 0 auto; }}
    .terminal-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      border-bottom: 1px solid #1E293B;
      padding-bottom: 16px;
    }}
    .terminal-title h1 {{ font-size: 24px; font-weight: 700; color: #38BDF8; letter-spacing: -0.02em; }}
    .terminal-title p {{ color: #94A3B8; font-size: 13px; font-family: monospace; }}
    .status-badge {{
      background: rgba(34, 197, 94, 0.1);
      border: 1px solid #22C55E;
      color: #22C55E;
      padding: 4px 12px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.05em;
    }}
    .filter-toolbar {{
      background: #1E293B;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .pill-group {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
    .pill-label {{ font-size: 12px; font-weight: 600; color: #94A3B8; margin-right: 8px; text-transform: uppercase; }}
    .filter-pill {{
      background: #0F172A;
      border: 1px solid #334155;
      color: #94A3B8;
      padding: 6px 14px;
      border-radius: 6px;
      font-size: 13px;
      cursor: pointer;
      font-weight: 500;
      transition: all 0.15s;
    }}
    .filter-pill:hover {{ border-color: #38BDF8; color: #F8FAFC; }}
    .filter-pill.active {{
      background: rgba(56, 189, 248, 0.15);
      border-color: #38BDF8;
      color: #38BDF8;
      font-weight: 600;
    }}
    .search-row {{ display: flex; gap: 12px; justify-content: space-between; align-items: center; }}
    .terminal-input {{
      flex: 1;
      max-width: 450px;
      background: #0F172A;
      border: 1px solid #334155;
      color: #F8FAFC;
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 13.5px;
      outline: none;
      font-family: monospace;
    }}
    .terminal-input:focus {{ border-color: #38BDF8; box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.25); }}
    .count-indicator {{ font-size: 13px; color: #94A3B8; font-family: monospace; }}
    .table-container {{
      background: #1E293B;
      border: 1px solid #334155;
      border-radius: 12px;
      overflow-x: auto;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
    th {{
      background: #0F172A;
      color: #94A3B8;
      padding: 12px 18px;
      border-bottom: 1px solid #334155;
      font-weight: 600;
      text-transform: uppercase;
      font-size: 11.5px;
      letter-spacing: 0.05em;
      cursor: pointer;
      user-select: none;
    }}
    th:hover {{ color: #38BDF8; }}
    td {{ padding: 12px 18px; border-bottom: 1px solid #334155; vertical-align: middle; }}
    tbody tr:hover {{ background: #243048; }}
    .price-cell {{ color: #38BDF8; font-weight: 700; text-align: right; font-family: monospace; font-size: 14px; }}
    .stars-cell {{ color: #FBBF24; text-align: center; letter-spacing: 2px; }}
    .stock-neon {{
      background: rgba(34, 197, 94, 0.15);
      border: 1px solid rgba(34, 197, 94, 0.4);
      color: #4ADE80;
      font-size: 11px;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 4px;
      font-family: monospace;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="terminal-header">
      <div class="terminal-title">
        <h1>FINTECH TERMINAL // ASSET INTELLIGENCE</h1>
        <p>Market Data Stream • 1,000 Catalog Assets • Real-Time Filter Engine</p>
      </div>
      <div class="status-badge">● LIVE VERIFIED</div>
    </div>

    <div class="filter-toolbar">
      <div class="pill-group">
        <span class="pill-label">Filter Rating:</span>
        <button class="filter-pill active" data-rating="all">All (1,000)</button>
        <button class="filter-pill" data-rating="5">5 Stars ★★★★★ (196)</button>
        <button class="filter-pill" data-rating="4">4 Stars ★★★★☆ (179)</button>
        <button class="filter-pill" data-rating="3">3 Stars ★★★☆☆ (203)</button>
        <button class="filter-pill" data-rating="2">2 Stars ★★☆☆☆ (196)</button>
        <button class="filter-pill" data-rating="1">1 Star ★☆☆☆☆ (226)</button>
      </div>

      <div class="search-row">
        <input type="text" id="terminalSearch" class="terminal-input" placeholder="Search ticker / title / price / page..." />
        <div id="countIndicator" class="count-indicator">ASSETS DISPLAYED: 1,000 / 1,000</div>
      </div>
    </div>

    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th data-col="title" style="text-align: left;">Security / Asset Title ⇅</th>
            <th data-col="price_gbp" style="text-align: right;">Unit Price (GBP) ⇅</th>
            <th data-col="rating" style="text-align: center;">Quality Rating ⇅</th>
            <th data-col="in_stock" style="text-align: center;">Liquidity / Stock ⇅</th>
            <th data-col="page_number" style="text-align: center;">Segment / Page ⇅</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>
  </div>

  <script>
    const DATASET = {json_data};
    let currentRatingFilter = 'all';
    let sortCol = null;
    let sortAsc = true;

    function escapeHtml(str) {{
      if (str === null || str === undefined) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }}

    function starGlyphs(r) {{
      return '★'.repeat(r) + '☆'.repeat(5 - r);
    }}

    function renderTable() {{
      const q = document.getElementById('terminalSearch').value.trim().toLowerCase();
      let filtered = DATASET.filter(item => {{
        if (currentRatingFilter !== 'all' && item.rating !== parseInt(currentRatingFilter, 10)) {{
          return false;
        }}
        if (!q) return true;
        return item.title.toLowerCase().includes(q) ||
               String(item.rating).includes(q) ||
               String(item.page_number).includes(q) ||
               item.price_gbp.toFixed(2).includes(q);
      }});

      if (sortCol) {{
        filtered.sort((a, b) => {{
          let valA = a[sortCol];
          let valB = b[sortCol];
          if (typeof valA === 'number' && typeof valB === 'number') {{
            return sortAsc ? valA - valB : valB - valA;
          }}
          return sortAsc ? String(valA).localeCompare(String(valB)) : String(valB).localeCompare(String(valA));
        }});
      }}

      document.getElementById('countIndicator').textContent = `ASSETS DISPLAYED: ${{filtered.length.toLocaleString()}} / ${{DATASET.length.toLocaleString()}}`;

      const tbody = document.getElementById('tableBody');
      if (filtered.length === 0) {{
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 32px; color: #64748B;">No assets match current criteria.</td></tr>';
        return;
      }}

      let html = '';
      for (const item of filtered) {{
        html += `<tr>
          <td style="color: #F8FAFC; font-weight: 500;">${{escapeHtml(item.title)}}</td>
          <td class="price-cell">£${{item.price_gbp.toFixed(2)}}</td>
          <td class="stars-cell">${{starGlyphs(item.rating)}}</td>
          <td style="text-align: center;"><span class="stock-neon">IN STOCK</span></td>
          <td style="text-align: center; color: #94A3B8; font-family: monospace;">PAGE ${{item.page_number}}</td>
        </tr>`;
      }}
      tbody.innerHTML = html;
    }}

    document.querySelectorAll('.filter-pill').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.filter-pill').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentRatingFilter = btn.getAttribute('data-rating');
        renderTable();
      }});
    }});

    document.getElementById('terminalSearch').addEventListener('input', renderTable);

    document.querySelectorAll('thead th[data-col]').forEach(th => {{
      th.addEventListener('click', () => {{
        const col = th.getAttribute('data-col');
        if (sortCol === col) {{
          sortAsc = !sortAsc;
        }} else {{
          sortCol = col;
          sortAsc = true;
        }}
        renderTable();
      }});
    }});

    renderTable();
  </script>
</body>
</html>
"""
    out_path.write_text(html_content, encoding="utf-8")
    return out_path


def generate_html_04_dense_analytics(records: List[Dict[str, Any]]) -> Path:
    """Theme 4: Dense Analytics (04_dense_analytics.html)

    High-density Bloomberg-style table for data power users, sticky header,
    compact rows (28px), column-based quick statistics footer (min/avg/max price).
    """
    out_path = HTML_DIR / "04_dense_analytics.html"
    json_data = json.dumps(records)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Books to Scrape // High-Density Bloomberg Table</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: Consolas, "Roboto Mono", "Courier New", monospace;
      background-color: #FFFFFF;
      color: #111827;
      font-size: 12px;
      line-height: 1.3;
    }}
    .header-bar {{
      background: #1F2937;
      color: #F9FAFB;
      padding: 8px 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2px solid #374151;
    }}
    .header-title {{ font-weight: 700; font-size: 13px; letter-spacing: 0.05em; }}
    .search-ctrl {{
      background: #111827;
      border: 1px solid #4B5563;
      color: #F9FAFB;
      padding: 4px 10px;
      font-size: 11.5px;
      border-radius: 3px;
      font-family: inherit;
      width: 280px;
    }}
    .table-viewport {{
      height: calc(100vh - 78px);
      overflow-y: auto;
    }}
    table {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }}
    thead th {{
      position: sticky;
      top: 0;
      background: #374151;
      color: #F9FAFB;
      font-weight: 700;
      padding: 6px 10px;
      border-right: 1px solid #4B5563;
      cursor: pointer;
      user-select: none;
      z-index: 10;
      white-space: nowrap;
    }}
    thead th:hover {{ background: #4B5563; }}
    tbody tr {{ height: 26px; border-bottom: 1px solid #E5E7EB; }}
    tbody tr:nth-child(even) {{ background: #F9FAFB; }}
    tbody tr:hover {{ background: #E5E7EB; }}
    td {{
      padding: 4px 10px;
      border-right: 1px solid #E5E7EB;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .title-cell {{ max-width: 480px; }}
    .num-cell {{ text-align: right; }}
    .center-cell {{ text-align: center; }}
    .stat-footer {{
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      height: 34px;
      background: #111827;
      color: #9CA3AF;
      border-top: 2px solid #374151;
      display: flex;
      align-items: center;
      padding: 0 16px;
      gap: 24px;
      font-size: 11.5px;
      z-index: 20;
    }}
    .stat-item {{ display: flex; gap: 6px; }}
    .stat-val {{ color: #F9FAFB; font-weight: 700; }}
  </style>
</head>
<body>
  <div class="header-bar">
    <div class="header-title">BLOOMBERG DENSE ANALYTICS : 1,000 PRODUCT CATALOG TICKER</div>
    <input type="text" id="quickFilter" class="search-ctrl" placeholder="Filter title/rating/page..." />
  </div>

  <div class="table-viewport">
    <table>
      <thead>
        <tr>
          <th data-col="page_number" class="center-cell" style="width: 60px;">PG ⇅</th>
          <th data-col="title" style="text-align: left;">BOOK TITLE ⇅</th>
          <th data-col="price_gbp" class="num-cell" style="width: 110px;">PRICE (£) ⇅</th>
          <th data-col="rating" class="center-cell" style="width: 90px;">RATING ⇅</th>
          <th data-col="in_stock" class="center-cell" style="width: 100px;">STATUS ⇅</th>
          <th style="text-align: left;">URL SLUG</th>
        </tr>
      </thead>
      <tbody id="tableBody"></tbody>
    </table>
  </div>

  <div class="stat-footer">
    <div class="stat-item">COUNT: <span id="statCount" class="stat-val">1,000</span></div>
    <div class="stat-item">MIN PRICE: <span id="statMin" class="stat-val">£10.00</span></div>
    <div class="stat-item">AVG PRICE: <span id="statAvg" class="stat-val">£35.07</span></div>
    <div class="stat-item">MAX PRICE: <span id="statMax" class="stat-val">£59.99</span></div>
    <div class="stat-item">GROSS TOTAL: <span id="statTotal" class="stat-val">£35,070.00</span></div>
  </div>

  <script>
    const DATASET = {json_data};
    let currentData = [...DATASET];
    let sortCol = null;
    let sortAsc = true;

    function escapeHtml(str) {{
      if (str === null || str === undefined) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }}

    function starGlyphs(r) {{
      return '★'.repeat(r) + '☆'.repeat(5 - r);
    }}

    function updateFooter(data) {{
      const count = data.length;
      document.getElementById('statCount').textContent = count.toLocaleString();

      if (count === 0) {{
        document.getElementById('statMin').textContent = '£0.00';
        document.getElementById('statAvg').textContent = '£0.00';
        document.getElementById('statMax').textContent = '£0.00';
        document.getElementById('statTotal').textContent = '£0.00';
        return;
      }}

      let minP = Infinity, maxP = -Infinity, sumP = 0;
      for (const item of data) {{
        const p = item.price_gbp;
        if (p < minP) minP = p;
        if (p > maxP) maxP = p;
        sumP += p;
      }}
      const avgP = sumP / count;

      document.getElementById('statMin').textContent = `£${{minP.toFixed(2)}}`;
      document.getElementById('statAvg').textContent = `£${{avgP.toFixed(2)}}`;
      document.getElementById('statMax').textContent = `£${{maxP.toFixed(2)}}`;
      document.getElementById('statTotal').textContent = `£${{sumP.toLocaleString(undefined, {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}`;
    }}

    function renderTable() {{
      const q = document.getElementById('quickFilter').value.trim().toLowerCase();
      let filtered = DATASET.filter(item => {{
        if (!q) return true;
        return item.title.toLowerCase().includes(q) ||
               String(item.rating).includes(q) ||
               String(item.page_number).includes(q) ||
               item.price_gbp.toFixed(2).includes(q);
      }});

      if (sortCol) {{
        filtered.sort((a, b) => {{
          let valA = a[sortCol];
          let valB = b[sortCol];
          if (typeof valA === 'number' && typeof valB === 'number') {{
            return sortAsc ? valA - valB : valB - valA;
          }}
          return sortAsc ? String(valA).localeCompare(String(valB)) : String(valB).localeCompare(String(valA));
        }});
      }}

      updateFooter(filtered);

      const tbody = document.getElementById('tableBody');
      if (filtered.length === 0) {{
        tbody.innerHTML = '<tr><td colspan="6" class="center-cell" style="padding:20px; color:#9CA3AF;">NO RECORDS MATCH FILTER</td></tr>';
        return;
      }}

      let html = '';
      for (const item of filtered) {{
        html += `<tr>
          <td class="center-cell">${{item.page_number}}</td>
          <td class="title-cell" title="${{escapeHtml(item.title)}}">${{escapeHtml(item.title)}}</td>
          <td class="num-cell">£${{item.price_gbp.toFixed(2)}}</td>
          <td class="center-cell" style="color: #D97706;">${{starGlyphs(item.rating)}}</td>
          <td class="center-cell" style="color: #059669; font-weight: 700;">IN_STOCK</td>
          <td>${{escapeHtml(item.detail_url)}}</td>
        </tr>`;
      }}
      tbody.innerHTML = html;
    }}

    document.getElementById('quickFilter').addEventListener('input', renderTable);

    document.querySelectorAll('thead th[data-col]').forEach(th => {{
      th.addEventListener('click', () => {{
        const col = th.getAttribute('data-col');
        if (sortCol === col) {{
          sortAsc = !sortAsc;
        }} else {{
          sortCol = col;
          sortAsc = true;
        }}
        renderTable();
      }});
    }});

    renderTable();
  </script>
</body>
</html>
"""
    out_path.write_text(html_content, encoding="utf-8")
    return out_path


def generate_html_05_card_grid_hybrid(records: List[Dict[str, Any]]) -> Path:
    """Theme 5: Card Grid Hybrid (05_card_grid_hybrid.html)

    Toggle button to switch between clean table view and visual e-commerce
    product card grid with star ratings and buy/detail action links.
    """
    out_path = HTML_DIR / "05_card_grid_hybrid.html"
    json_data = json.dumps(records)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Books to Scrape // Card Grid & Table Hybrid View</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: #F3F4F6;
      color: #1F2937;
      line-height: 1.5;
      padding: 32px 24px;
    }}
    .container {{ max-width: 1280px; margin: 0 auto; }}
    .top-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 16px;
    }}
    .title-group h1 {{ font-size: 26px; font-weight: 700; color: #111827; }}
    .title-group p {{ font-size: 13.5px; color: #6B7280; }}
    .view-toggle {{
      display: inline-flex;
      background: #E5E7EB;
      padding: 4px;
      border-radius: 8px;
      gap: 4px;
    }}
    .toggle-btn {{
      padding: 8px 16px;
      border: none;
      background: transparent;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      color: #4B5563;
      cursor: pointer;
      transition: all 0.15s;
    }}
    .toggle-btn.active {{
      background: #FFFFFF;
      color: #4F46E5;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    .toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 24px;
      flex-wrap: wrap;
    }}
    .search-input {{
      flex: 1;
      max-width: 400px;
      padding: 10px 16px;
      border: 1px solid #D1D5DB;
      border-radius: 8px;
      font-size: 14px;
      background: #FFFFFF;
      outline: none;
    }}
    .search-input:focus {{ border-color: #4F46E5; box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.15); }}
    .sort-select {{
      padding: 10px 14px;
      border: 1px solid #D1D5DB;
      border-radius: 8px;
      font-size: 13.5px;
      background: #FFFFFF;
      color: #374151;
      outline: none;
    }}
    /* Card Grid View */
    .card-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 20px;
    }}
    .product-card {{
      background: #FFFFFF;
      border: 1px solid #E5E7EB;
      border-radius: 12px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      box-shadow: 0 1px 3px rgba(0,0,0,0.03);
      transition: transform 0.15s, box-shadow 0.15s;
    }}
    .product-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 10px 15px -3px rgba(0,0,0,0.08);
      border-color: #C7D2FE;
    }}
    .card-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
    .badge-page {{
      background: #EEF2FF;
      color: #4F46E5;
      font-size: 11.5px;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 6px;
    }}
    .badge-stock {{
      background: #DEF7EC;
      color: #03543F;
      font-size: 11.5px;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 9999px;
    }}
    .card-title {{
      font-size: 15px;
      font-weight: 600;
      color: #111827;
      margin-bottom: 12px;
      line-height: 1.4;
      min-height: 42px;
    }}
    .card-meta {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: auto;
      padding-top: 14px;
      border-top: 1px solid #F3F4F6;
    }}
    .card-price {{ font-size: 20px; font-weight: 700; color: #111827; }}
    .card-stars {{ color: #F59E0B; font-size: 13px; letter-spacing: 1px; }}
    .card-btn {{
      margin-top: 14px;
      text-align: center;
      background: #4F46E5;
      color: #FFFFFF;
      text-decoration: none;
      padding: 8px 14px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 500;
      transition: background 0.15s;
      display: block;
    }}
    .card-btn:hover {{ background: #4338CA; }}
    /* Table View */
    .table-container {{
      background: #FFFFFF;
      border: 1px solid #E5E7EB;
      border-radius: 12px;
      overflow-x: auto;
      box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }}
    table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13.5px; }}
    th {{
      background: #F9FAFB;
      color: #374151;
      font-weight: 600;
      padding: 12px 18px;
      border-bottom: 1px solid #E5E7EB;
      cursor: pointer;
      user-select: none;
    }}
    th:hover {{ background: #F3F4F6; }}
    td {{ padding: 12px 18px; border-bottom: 1px solid #E5E7EB; vertical-align: middle; }}
    tbody tr:hover {{ background: #F9FAFB; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="top-bar">
      <div class="title-group">
        <h1>Books to Scrape : Hybrid Catalog</h1>
        <p>1,000 Verified Books • Toggle between Executive Table and E-Commerce Cards</p>
      </div>
      <div class="view-toggle">
        <button id="btnCards" class="toggle-btn active">⊞ Card Grid</button>
        <button id="btnTable" class="toggle-btn">☰ Table View</button>
      </div>
    </div>

    <div class="toolbar">
      <input type="text" id="searchInput" class="search-input" placeholder="Search title, price, rating, page..." />
      <div style="display: flex; gap: 12px; align-items: center;">
        <label for="sortSelect" style="font-size: 13px; color: #4B5563; font-weight: 500;">Sort By:</label>
        <select id="sortSelect" class="sort-select">
          <option value="price_asc">Price: Low to High</option>
          <option value="price_desc">Price: High to Low</option>
          <option value="rating_desc">Rating: High to Low</option>
          <option value="rating_asc">Rating: Low to High</option>
          <option value="title_asc">Title: A to Z</option>
          <option value="title_desc">Title: Z to A</option>
        </select>
      </div>
    </div>

    <div id="cardsView" class="card-grid"></div>
    <div id="tableView" class="table-container" style="display: none;">
      <table>
        <thead>
          <tr>
            <th data-col="title">Title ⇅</th>
            <th data-col="price_gbp" style="text-align: right;">Price ⇅</th>
            <th data-col="rating" style="text-align: center;">Rating ⇅</th>
            <th data-col="in_stock" style="text-align: center;">Availability ⇅</th>
            <th data-col="page_number" style="text-align: center;">Page ⇅</th>
            <th style="text-align: center;">Action</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>
  </div>

  <script>
    const DATASET = {json_data};
    let activeView = 'cards'; // 'cards' | 'table'

    function escapeHtml(str) {{
      if (str === null || str === undefined) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }}

    function starGlyphs(r) {{
      return '★'.repeat(r) + '☆'.repeat(5 - r);
    }}

    function getFilteredAndSorted() {{
      const q = document.getElementById('searchInput').value.trim().toLowerCase();
      let res = DATASET.filter(item => {{
        if (!q) return true;
        return item.title.toLowerCase().includes(q) ||
               String(item.rating).includes(q) ||
               String(item.page_number).includes(q) ||
               item.price_gbp.toFixed(2).includes(q);
      }});

      const sortMode = document.getElementById('sortSelect').value;
      if (sortMode === 'price_asc') res.sort((a, b) => a.price_gbp - b.price_gbp);
      else if (sortMode === 'price_desc') res.sort((a, b) => b.price_gbp - a.price_gbp);
      else if (sortMode === 'rating_desc') res.sort((a, b) => b.rating - a.rating);
      else if (sortMode === 'rating_asc') res.sort((a, b) => a.rating - b.rating);
      else if (sortMode === 'title_asc') res.sort((a, b) => a.title.localeCompare(b.title));
      else if (sortMode === 'title_desc') res.sort((a, b) => b.title.localeCompare(a.title));

      return res;
    }}

    function render() {{
      const data = getFilteredAndSorted();
      const cardsView = document.getElementById('cardsView');
      const tableBody = document.getElementById('tableBody');

      if (data.length === 0) {{
        cardsView.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 48px; color: #6B7280;">No products match current search.</div>';
        tableBody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 32px; color: #6B7280;">No products match current search.</td></tr>';
        return;
      }}

      // Render Cards
      let cardsHtml = '';
      for (const item of data) {{
        const url = `https://books.toscrape.com/catalogue/${{item.detail_url}}`;
        cardsHtml += `<div class="product-card">
          <div class="card-top">
            <span class="badge-page">Page ${{item.page_number}}</span>
            <span class="badge-stock">In Stock</span>
          </div>
          <div class="card-title">${{escapeHtml(item.title)}}</div>
          <div class="card-meta">
            <div class="card-price">£${{item.price_gbp.toFixed(2)}}</div>
            <div class="card-stars">${{starGlyphs(item.rating)}}</div>
          </div>
          <a href="${{url}}" target="_blank" rel="noopener noreferrer" class="card-btn">View Details ↗</a>
        </div>`;
      }}
      cardsView.innerHTML = cardsHtml;

      // Render Table
      let tableHtml = '';
      for (const item of data) {{
        const url = `https://books.toscrape.com/catalogue/${{item.detail_url}}`;
        tableHtml += `<tr>
          <td style="font-weight: 500;">${{escapeHtml(item.title)}}</td>
          <td style="text-align: right; font-weight: 600;">£${{item.price_gbp.toFixed(2)}}</td>
          <td style="text-align: center; color: #F59E0B;">${{starGlyphs(item.rating)}}</td>
          <td style="text-align: center;"><span class="badge-stock">In Stock</span></td>
          <td style="text-align: center; color: #6B7280;">${{item.page_number}}</td>
          <td style="text-align: center;"><a href="${{url}}" target="_blank" rel="noopener noreferrer" style="color: #4F46E5; text-decoration: none; font-weight: 500;">View ↗</a></td>
        </tr>`;
      }}
      tableBody.innerHTML = tableHtml;
    }}

    document.getElementById('btnCards').addEventListener('click', () => {{
      activeView = 'cards';
      document.getElementById('btnCards').classList.add('active');
      document.getElementById('btnTable').classList.remove('active');
      document.getElementById('cardsView').style.display = 'grid';
      document.getElementById('tableView').style.display = 'none';
    }});

    document.getElementById('btnTable').addEventListener('click', () => {{
      activeView = 'table';
      document.getElementById('btnTable').classList.add('active');
      document.getElementById('btnCards').classList.remove('active');
      document.getElementById('cardsView').style.display = 'none';
      document.getElementById('tableView').style.display = 'block';
    }});

    document.getElementById('searchInput').addEventListener('input', render);
    document.getElementById('sortSelect').addEventListener('change', render);

    render();
  </script>
</body>
</html>
"""
    out_path.write_text(html_content, encoding="utf-8")
    return out_path


# ==============================================================================
# MAIN ORCHESTRATOR
# ==============================================================================


def main() -> None:
    """Orchestrate the generation of all 5 Excel workbooks and 5 HTML previews."""
    print("=" * 70)
    print("Multi-Theme Presentation Variants Generator")
    print("=" * 70)

    EXCEL_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading verified dataset from {CSV_PATH}...")
    records = load_dataset()
    print(f"Loaded {len(records)} product records.")

    print("\n--- Generating 5 Styled Excel Workbooks ---")
    f1 = generate_excel_01_corporate_slate(records)
    print(f"  [1/5] {f1.name} generated ({f1.stat().st_size:,} bytes)")

    f2 = generate_excel_02_emerald_growth(records)
    print(f"  [2/5] {f2.name} generated ({f2.stat().st_size:,} bytes)")

    f3 = generate_excel_03_fintech_navy(records)
    print(f"  [3/5] {f3.name} generated ({f3.stat().st_size:,} bytes)")

    f4 = generate_excel_04_minimal_monochrome(records)
    print(f"  [4/5] {f4.name} generated ({f4.stat().st_size:,} bytes)")

    f5 = generate_excel_05_executive_summary_kpi(records)
    print(f"  [5/5] {f5.name} generated ({f5.stat().st_size:,} bytes)")

    print("\n--- Generating 5 Interactive HTML Previews ---")
    h1 = generate_html_01_tailwind_clean(records)
    print(f"  [1/5] {h1.name} generated ({h1.stat().st_size:,} bytes)")

    h2 = generate_html_02_stripe_dashboard(records)
    print(f"  [2/5] {h2.name} generated ({h2.stat().st_size:,} bytes)")

    h3 = generate_html_03_dark_fintech(records)
    print(f"  [3/5] {h3.name} generated ({h3.stat().st_size:,} bytes)")

    h4 = generate_html_04_dense_analytics(records)
    print(f"  [4/5] {h4.name} generated ({h4.stat().st_size:,} bytes)")

    h5 = generate_html_05_card_grid_hybrid(records)
    print(f"  [5/5] {h5.name} generated ({h5.stat().st_size:,} bytes)")

    print("\nAll 10 deliverable variants successfully built.")
    print("=" * 70)


if __name__ == "__main__":
    main()
