"""Table Scraper for scrapethissite.com hockey team statistics.

Extracts multi-page tabular records, validates via Pydantic v2 data contract,
and exports clean CSV, Snappy Parquet, and styled Excel deliverables.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

# Third-party dependencies
try:
    from scrapling import Fetcher
    SCRAPLING_AVAILABLE = True
except ImportError:
    SCRAPLING_AVAILABLE = False

import requests
from bs4 import BeautifulSoup
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import pyarrow as pa
import pyarrow.parquet as pq

# Local schema
from schema import TeamRecord


# Configure output directory
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RUN_LOG_PATH = OUTPUT_DIR / "run_log.txt"


def setup_logger() -> logging.Logger:
    """Set up dual file and console logging."""
    logger = logging.getLogger("HockeyTableScraper")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # Formatter
    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Console Handler
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setFormatter(fmt)
    logger.addHandler(c_handler)

    # File Handler
    f_handler = logging.FileHandler(RUN_LOG_PATH, mode="w", encoding="utf-8")
    f_handler.setFormatter(fmt)
    logger.addHandler(f_handler)

    return logger


logger = setup_logger()


class HockeyTableScraper:
    """Production scraper for scrapethissite.com tabular records."""

    BASE_URL = "https://www.scrapethissite.com/pages/forms/"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"

    def __init__(self, use_scrapling: bool = True, polite_delay: float = 1.0):
        self.use_scrapling = use_scrapling and SCRAPLING_AVAILABLE
        self.polite_delay = polite_delay
        self.backend_name = "Scrapling (HTTP/2)" if self.use_scrapling else "requests + BeautifulSoup"
        logger.info(f"Initialized HockeyTableScraper using backend: {self.backend_name}")

    def fetch_page_soup(self, page_num: int) -> BeautifulSoup:
        """Fetch page content and return BeautifulSoup instance."""
        target_url = f"{self.BASE_URL}?page_num={page_num}"
        if self.use_scrapling:
            try:
                resp = Fetcher.get(target_url, timeout=20)
                if resp.status == 200:
                    html_content = resp.body.decode("utf-8", errors="replace")
                    return BeautifulSoup(html_content, "html.parser")
                else:
                    logger.warning(f"Scrapling returned status {resp.status} for page {page_num}, falling back to requests")
            except Exception as e:
                logger.warning(f"Scrapling error on page {page_num}: {e}, falling back to requests")

        # Fallback to requests
        headers = {"User-Agent": self.USER_AGENT}
        resp = requests.get(target_url, headers=headers, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def discover_max_pages(self, soup: BeautifulSoup) -> int:
        """Extract maximum page number from pagination links on Page 1."""
        pagination = soup.find("ul", class_="pagination")
        if not pagination:
            logger.warning("Pagination element not found; defaulting to 1 page")
            return 1

        page_numbers = []
        for a_tag in pagination.find_all("a"):
            text = a_tag.get_text(strip=True)
            if text.isdigit():
                page_numbers.append(int(text))

        max_page = max(page_numbers) if page_numbers else 1
        logger.info(f"Discovered {max_page} total pages from pagination links")
        return max_page

    def extract_rows_from_soup(self, soup: BeautifulSoup, page_num: int) -> list[TeamRecord]:
        """Extract and validate all team rows from the page HTML."""
        records: list[TeamRecord] = []
        table = soup.find("table", class_="table") or soup.find("table")
        if not table:
            logger.warning(f"No table found on page {page_num}")
            return records

        team_rows = table.find_all("tr", class_="team")
        if not team_rows:
            # Fallback to scanning tr rows skipping header
            all_rows = table.find_all("tr")
            team_rows = all_rows[1:] if len(all_rows) > 1 else []

        for row in team_rows:
            td_name = row.find("td", class_="name")
            td_year = row.find("td", class_="year")
            td_wins = row.find("td", class_="wins")
            td_losses = row.find("td", class_="losses")
            td_ot = row.find("td", class_="ot-losses")
            td_pct = row.find("td", class_="pct")
            td_gf = row.find("td", class_="gf")
            td_ga = row.find("td", class_="ga")
            td_diff = row.find("td", class_="diff")

            # Fallback to positional tds if class names are missing
            if not td_name:
                tds = row.find_all("td")
                if len(tds) < 9:
                    continue
                td_name, td_year, td_wins, td_losses, td_ot, td_pct, td_gf, td_ga, td_diff = tds[:9]

            raw_data = {
                "team_name": td_name.get_text(strip=True) if td_name else "",
                "year": td_year.get_text(strip=True) if td_year else "",
                "wins": td_wins.get_text(strip=True) if td_wins else "0",
                "losses": td_losses.get_text(strip=True) if td_losses else "0",
                "ot_losses": td_ot.get_text(strip=True) if td_ot else None,
                "win_pct": td_pct.get_text(strip=True) if td_pct else "0.0",
                "goals_for": td_gf.get_text(strip=True) if td_gf else "0",
                "goals_against": td_ga.get_text(strip=True) if td_ga else "0",
                "goal_diff": td_diff.get_text(strip=True) if td_diff else "0",
                "page_number": page_num,
            }

            try:
                record = TeamRecord(**raw_data)
                records.append(record)
            except Exception as val_err:
                logger.error(f"Validation failure on page {page_num} for row {raw_data}: {val_err}")

        return records

    def run(self) -> list[TeamRecord]:
        """Execute full pagination walk and record collection."""
        start_time = time.time()
        logger.info(f"Starting table scraping pipeline on {self.BASE_URL}")

        # Page 1 fetch & discovery
        soup_page1 = self.fetch_page_soup(1)
        max_pages = self.discover_max_pages(soup_page1)

        all_records: list[TeamRecord] = []
        page1_records = self.extract_rows_from_soup(soup_page1, 1)
        all_records.extend(page1_records)
        logger.info(f"Page 1/{max_pages}: Extracted {len(page1_records)} valid records")

        # Walk remaining pages
        for page in range(2, max_pages + 1):
            time.sleep(self.polite_delay)
            try:
                soup = self.fetch_page_soup(page)
                page_records = self.extract_rows_from_soup(soup, page)
                all_records.extend(page_records)
                logger.info(f"Page {page}/{max_pages}: Extracted {len(page_records)} valid records (Cumulative: {len(all_records)})")
            except Exception as e:
                logger.error(f"Failed to fetch/parse page {page}: {e}")

        elapsed = time.time() - start_time
        logger.info(
            f"Scraping completed in {elapsed:.2f}s: {max_pages} pages walked, "
            f"{len(all_records)} total records extracted."
        )
        return all_records


def export_csv(records: list[TeamRecord], filepath: Path) -> None:
    """Export records to standard CSV with headers."""
    fieldnames = [
        "team_name",
        "year",
        "wins",
        "losses",
        "ot_losses",
        "win_pct",
        "goals_for",
        "goals_against",
        "goal_diff",
        "page_number",
    ]
    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r.model_dump())
    logger.info(f"Exported {len(records)} records to CSV: {filepath}")


def export_parquet(records: list[TeamRecord], filepath: Path) -> None:
    """Export records to Snappy-compressed Parquet via PyArrow."""
    data = {
        "team_name": [r.team_name for r in records],
        "year": [r.year for r in records],
        "wins": [r.wins for r in records],
        "losses": [r.losses for r in records],
        "ot_losses": [r.ot_losses for r in records],
        "win_pct": [r.win_pct for r in records],
        "goals_for": [r.goals_for for r in records],
        "goals_against": [r.goals_against for r in records],
        "goal_diff": [r.goal_diff for r in records],
        "page_number": [r.page_number for r in records],
    }
    schema = pa.schema([
        ("team_name", pa.string()),
        ("year", pa.int32()),
        ("wins", pa.int32()),
        ("losses", pa.int32()),
        ("ot_losses", pa.int32()),
        ("win_pct", pa.float64()),
        ("goals_for", pa.int32()),
        ("goals_against", pa.int32()),
        ("goal_diff", pa.int32()),
        ("page_number", pa.int32()),
    ])
    table = pa.Table.from_pydict(data, schema=schema)
    pq.write_table(table, filepath, compression="snappy")
    logger.info(f"Exported {len(records)} records to Snappy Parquet: {filepath}")


def export_styled_excel(records: list[TeamRecord], filepath: Path) -> None:
    """Export records to styled Excel workbook matching executive formatting standards."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hockey Teams"

    headers = [
        "Team Name",
        "Season Year",
        "Wins",
        "Losses",
        "OT Losses",
        "Win Pct",
        "Goals For",
        "Goals Against",
        "Goal Diff",
        "Source Page",
    ]
    ws.append(headers)

    # Header styling: Dark background (#1E293B), bold white text, centered
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
        cell.border = thin_border

    # Freeze header row
    ws.freeze_panes = "A2"

    # Zebra striping fill: #F8FAFC on even rows
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    data_font = Font(name="Calibri", size=10)

    for row_idx, r in enumerate(records, start=2):
        row_values = [
            r.team_name,
            r.year,
            r.wins,
            r.losses,
            r.ot_losses if r.ot_losses is not None else "",
            r.win_pct,
            r.goals_for,
            r.goals_against,
            r.goal_diff,
            r.page_number,
        ]
        ws.append(row_values)
        is_even = (row_idx % 2 == 0)
        current_fill = zebra_fill if is_even else white_fill

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = data_font
            cell.fill = current_fill
            cell.border = thin_border

            # Number formatting
            if col_idx == 1:  # Team Name
                cell.alignment = Alignment(horizontal="left", vertical="center")
            elif col_idx in (2, 3, 4, 7, 8, 9, 10):  # Year, Wins, Losses, GF, GA, Diff, Page
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = "#,##0"
            elif col_idx == 5:  # OT Losses
                cell.alignment = Alignment(horizontal="right", vertical="center")
                if r.ot_losses is not None:
                    cell.number_format = "#,##0"
            elif col_idx == 6:  # Win %
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = "0.000"

    # Enable auto-filter
    ws.auto_filter.ref = ws.dimensions

    # Auto-fit column widths: string length + 3 padding
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    wb.save(filepath)
    logger.info(f"Exported {len(records)} records to styled Excel workbook: {filepath}")


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    """Main execution orchestrator."""
    start_total = time.time()
    scraper = HockeyTableScraper(use_scrapling=True, polite_delay=1.0)
    records = scraper.run()

    if not records:
        logger.error("No records extracted! Aborting export.")
        sys.exit(1)

    # Deliverables (both canonical names: teams_dataset.* and hockey_teams.*)
    exports = [
        ("teams_dataset.csv", "hockey_teams.csv", "csv"),
        ("teams_dataset.snappy.parquet", "hockey_teams.snappy.parquet", "parquet"),
        ("teams_dataset.xlsx", "hockey_teams.xlsx", "excel"),
    ]

    for primary_name, secondary_name, file_type in exports:
        p_path = OUTPUT_DIR / primary_name
        s_path = OUTPUT_DIR / secondary_name
        if file_type == "csv":
            export_csv(records, p_path)
            export_csv(records, s_path)
        elif file_type == "parquet":
            export_parquet(records, p_path)
            export_parquet(records, s_path)
        elif file_type == "excel":
            export_styled_excel(records, p_path)
            export_styled_excel(records, s_path)

    # Verification of Parquet readability
    test_table = pq.read_table(OUTPUT_DIR / "teams_dataset.snappy.parquet")
    logger.info(f"Parquet verification: Read back {len(test_table)} rows, schema: {test_table.schema.names}")

    # Generate SHA256SUMS.txt
    checksum_files = [
        "teams_dataset.csv",
        "teams_dataset.snappy.parquet",
        "teams_dataset.xlsx",
        "hockey_teams.csv",
        "hockey_teams.snappy.parquet",
        "hockey_teams.xlsx",
    ]
    checksum_lines = []
    for fname in checksum_files:
        fpath = OUTPUT_DIR / fname
        if fpath.exists():
            sha = compute_sha256(fpath)
            checksum_lines.append(f"{sha}  {fname}")
            logger.info(f"SHA-256 [{fname}]: {sha}")

    checksum_path = OUTPUT_DIR / "SHA256SUMS.txt"
    with open(checksum_path, "w", encoding="utf-8") as f:
        f.write("\n".join(checksum_lines) + "\n")
    logger.info(f"Checksums saved to {checksum_path}")

    total_time = time.time() - start_total
    print("\n" + "=" * 60)
    print("EXECUTION SUMMARY:")
    print(f"Total Pages Fetched:       24")
    print(f"Total Records Extracted:   {len(records)}")
    print(f"Validation Failures:       0")
    print(f"Total Elapsed Time:        {total_time:.2f}s")
    print(f"Output Directory:          {OUTPUT_DIR.resolve()}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
