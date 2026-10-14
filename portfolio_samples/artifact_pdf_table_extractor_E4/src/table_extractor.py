"""Table grid extraction, multi-line item merger, and schema drift handler.
Strict zero em dash policy enforced.
"""
from typing import List, Dict, Any, Optional
from decimal import Decimal
import re
from src.models import InvoiceLineItem


class TableExtractor:
    """Extracts structured line items from detected tabular text grids."""

    def __init__(self):
        self.drift_detected: bool = False
        self.multiline_merges_applied: int = 0

    def parse_table_grid(self, raw_rows: List[List[str]]) -> List[InvoiceLineItem]:
        """Convert raw 2D grid into typed InvoiceLineItem list, merging multi-line rows."""
        if not raw_rows or len(raw_rows) < 2:
            return []

        header = [col.strip().lower() for col in raw_rows[0]]
        col_indices = self._resolve_header_columns(header)

        items: List[InvoiceLineItem] = []
        pending_item: Optional[InvoiceLineItem] = None
        line_num = 1

        for row in raw_rows[1:]:
            if not any(row):
                continue

            desc_val = row[col_indices["desc"]].strip() if col_indices["desc"] < len(row) else ""
            qty_val = row[col_indices["qty"]].strip() if col_indices["qty"] < len(row) else ""
            price_val = row[col_indices["price"]].strip() if col_indices["price"] < len(row) else ""
            total_val = row[col_indices["total"]].strip() if col_indices["total"] < len(row) else ""

            # Check if this row is a continuation of previous line item description
            is_continuation = desc_val and not qty_val and not price_val and not total_val
            if is_continuation and pending_item is not None:
                pending_item.item_description += " " + desc_val
                self.multiline_merges_applied += 1
                continue

            parsed_qty = self._parse_decimal(qty_val)
            parsed_price = self._parse_decimal(price_val)
            parsed_total = self._parse_decimal(total_val)

            if parsed_qty is not None and parsed_price is not None and parsed_total is not None:
                if pending_item:
                    items.append(pending_item)

                sku = (
                    row[col_indices["sku"]].strip()
                    if col_indices.get("sku") is not None and col_indices["sku"] < len(row)
                    else None
                )
                pending_item = InvoiceLineItem(
                    item_description=desc_val,
                    quantity=parsed_qty,
                    unit_price=parsed_price,
                    total_amount=parsed_total,
                    sku_code=sku,
                    line_number=line_num,
                )
                line_num += 1

        if pending_item:
            items.append(pending_item)

        return items

    def _resolve_header_columns(self, header: List[str]) -> Dict[str, int]:
        """Detect column indexes tolerant to header naming drift."""
        mapping: Dict[str, int] = {}
        for idx, col in enumerate(header):
            if any(term in col for term in ["desc", "item", "product", "details", "particulars"]):
                mapping["desc"] = idx
            elif any(term in col for term in ["qty", "quantity", "units", "count"]):
                mapping["qty"] = idx
            elif any(term in col for term in ["price", "rate", "unit", "cost"]):
                mapping["price"] = idx
            elif any(term in col for term in ["total", "amount", "line total", "net"]):
                mapping["total"] = idx
            elif any(term in col for term in ["sku", "code", "part", "item#"]):
                mapping["sku"] = idx

        # Defaults if headers drifted
        if "desc" not in mapping:
            self.drift_detected = True
            mapping["desc"] = 0
        if "qty" not in mapping:
            self.drift_detected = True
            mapping["qty"] = 1
        if "price" not in mapping:
            self.drift_detected = True
            mapping["price"] = 2
        if "total" not in mapping:
            self.drift_detected = True
            mapping["total"] = 3

        return mapping

    @staticmethod
    def _parse_decimal(val: str) -> Optional[Decimal]:
        """Parse formatted currency string into Decimal, handling US and European styles."""
        if not val:
            return None
        cleaned = re.sub(r"[^0-9.,-]", "", val)
        if not cleaned:
            return None
        # Handle European 1.234,56 vs US 1,234.56
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        try:
            return Decimal(cleaned)
        except Exception:
            return None
