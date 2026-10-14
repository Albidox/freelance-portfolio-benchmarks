"""PDF layout parser and geometric bounding box clusterer.
Uses pure standard and portable libraries without heavy external native dependencies.
Strict zero em dash policy enforced.
"""
import math
from typing import List, Dict, Any, Optional, Tuple, Union


class PDFLayoutParser:
    """Extracts raw text blocks, coordinates, and identifies tabular gutters."""

    def __init__(self, horizontal_tolerance: float = 3.0, vertical_tolerance: float = 2.0):
        self.horizontal_tolerance = horizontal_tolerance
        self.vertical_tolerance = vertical_tolerance
        self.parsed_pages_count: int = 0
        self.corrupt_files_detected: int = 0
        self.fatal_crashes: int = 0

    def inspect_stream_integrity(self, pdf_bytes: bytes) -> bool:
        """Validate PDF magic bytes and stream termination."""
        if not pdf_bytes or len(pdf_bytes) < 32:
            self.corrupt_files_detected += 1
            return False
        if not pdf_bytes.startswith(b"%PDF-"):
            self.corrupt_files_detected += 1
            return False
        if b"%%EOF" not in pdf_bytes[-1024:]:
            # Truncated or missing EOF marker
            self.corrupt_files_detected += 1
            return False
        return True

    def cluster_words_into_lines(self, word_boxes: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Group word bounding boxes into horizontal text lines based on y0/top coordinates."""
        if not word_boxes:
            return []

        sorted_boxes = sorted(word_boxes, key=lambda b: (round(b.get("top", 0.0), 1), b.get("x0", 0.0)))
        lines: List[List[Dict[str, Any]]] = []
        current_line: List[Dict[str, Any]] = []
        current_top: Optional[float] = None

        for box in sorted_boxes:
            top = float(box.get("top", 0.0))
            if current_top is None:
                current_top = top
                current_line.append(box)
            elif abs(top - current_top) <= self.vertical_tolerance:
                current_line.append(box)
            else:
                lines.append(sorted(current_line, key=lambda b: float(b.get("x0", 0.0))))
                current_line = [box]
                current_top = top

        if current_line:
            lines.append(sorted(current_line, key=lambda b: float(b.get("x0", 0.0))))

        return lines

    def detect_column_gutters(self, elements: Union[List[Dict[str, Any]], List[List[Dict[str, Any]]]]) -> List[float]:
        """Detect recurring vertical gutters separating table columns."""
        if not elements:
            return []

        x_positions: List[float] = []
        for elem in elements:
            if isinstance(elem, dict):
                x_positions.append(float(elem.get("x0", 0.0)))
            elif isinstance(elem, list):
                for box in elem:
                    if isinstance(box, dict):
                        x_positions.append(float(box.get("x0", 0.0)))

        if not x_positions:
            return []

        x_positions.sort()
        gutters: List[float] = []
        cluster_start = x_positions[0]
        cluster: List[float] = [cluster_start]

        for x in x_positions[1:]:
            if x - cluster[-1] <= self.horizontal_tolerance * 2:
                cluster.append(x)
            else:
                gutters.append(sum(cluster) / len(cluster))
                cluster = [x]

        if cluster:
            gutters.append(sum(cluster) / len(cluster))

        return gutters

    def reconstruct_table_rows(
        self,
        lines: List[List[Dict[str, Any]]],
        gutters: List[float],
    ) -> List[List[str]]:
        """Map line elements into discrete tabular grid cells using detected gutters."""
        grid: List[List[str]] = []
        if not gutters:
            return [[ " ".join(box.get("text", "") for box in line) ] for line in lines]

        for line in lines:
            row_cells = ["" for _ in range(len(gutters))]
            for box in line:
                x = float(box.get("x0", 0.0))
                text = str(box.get("text", "")).strip()
                if not text:
                    continue
                # Find nearest gutter column
                best_col = 0
                min_dist = float("inf")
                for col_idx, g_x in enumerate(gutters):
                    dist = abs(x - g_x)
                    if dist < min_dist:
                        min_dist = dist
                        best_col = col_idx
                if row_cells[best_col]:
                    row_cells[best_col] += " " + text
                else:
                    row_cells[best_col] = text
            if any(cell.strip() for cell in row_cells):
                grid.append(row_cells)

        return grid
