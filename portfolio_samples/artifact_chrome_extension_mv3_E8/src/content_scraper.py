"""DOM content scraper, heuristic table detector, and CSV formula injection sanitizer."""
import re
from typing import Dict, Any, List, Optional, Tuple


class DOMContentScraper:
    def __init__(self):
        self.sanitized_cells_count: int = 0

    @staticmethod
    def sanitize_csv_cell(value: Any) -> str:
        """Neutralize CSV formula injection attacks by prepending single quote.
        Neutralizes leading '=', '+', '-', '@', tab, and carriage return.
        """
        if value is None:
            return ""
        s = str(value).strip()
        if not s:
            return ""

        # Check for dangerous spreadsheet execution prefixes
        if s[0] in ("=", "+", "-", "@", "\t") or ord(s[0]) == 13:
            return "'" + s
        return s

    def sanitize_record(self, raw_record: Dict[str, Any]) -> Dict[str, str]:
        """Sanitize all attributes within a scraped row dictionary."""
        sanitized = {}
        for key, val in raw_record.items():
            clean_val = self.sanitize_csv_cell(val)
            if clean_val != str(val).strip():
                self.sanitized_cells_count += 1
            sanitized[key] = clean_val
        return sanitized

    def parse_html_table(self, html_snippet: str) -> List[Dict[str, str]]:
        """Heuristic HTML table parser extracting header-mapped rows."""
        # Clean HTML table tag search
        row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
        cell_pattern = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.DOTALL | re.IGNORECASE)
        tag_strip_pattern = re.compile(r"<[^>]+>")

        rows = row_pattern.findall(html_snippet)
        if not rows:
            return []

        headers = []
        parsed_records = []

        # Parse first row as headers if available
        first_row_cells = cell_pattern.findall(rows[0])
        headers = [tag_strip_pattern.sub("", c).strip() for c in first_row_cells]

        for r in rows[1:]:
            cells = cell_pattern.findall(r)
            if not cells:
                continue
            clean_cells = [tag_strip_pattern.sub("", c).strip() for c in cells]
            record = {}
            for i, val in enumerate(clean_cells):
                col_name = headers[i] if i < len(headers) else f"column_{i+1}"
                record[col_name] = self.sanitize_csv_cell(val)
            parsed_records.append(record)

        return parsed_records
