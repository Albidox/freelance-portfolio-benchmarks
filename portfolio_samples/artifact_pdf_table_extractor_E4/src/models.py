"""Data models and validation contracts for Legacy PDF Invoice Extractor.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from decimal import Decimal, ROUND_HALF_UP
import re
from datetime import datetime, timezone

CURRENCY_REGEX = re.compile(r"[$€£₹¥]|USD|EUR|GBP|INR")


@dataclass
class InvoiceLineItem:
    """Represents an individual line item extracted from an invoice table."""
    item_description: str
    quantity: Decimal
    unit_price: Decimal
    total_amount: Decimal
    sku_code: Optional[str] = None
    tax_rate: Optional[Decimal] = None
    line_number: int = 1

    def validate_math(self, tolerance: Decimal = Decimal("0.05")) -> bool:
        """Verify quantity * unit_price == total_amount within tolerance."""
        calculated = (self.quantity * self.unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        diff = abs(calculated - self.total_amount)
        return diff <= tolerance

    def to_dict(self) -> Dict[str, Any]:
        """Serialize line item to dictionary with float-casted numeric fields."""
        return {
            "item_description": self.item_description,
            "quantity": float(self.quantity),
            "unit_price": float(self.unit_price),
            "total_amount": float(self.total_amount),
            "sku_code": self.sku_code,
            "tax_rate": float(self.tax_rate) if self.tax_rate is not None else None,
            "line_number": self.line_number,
        }


# Canonical alias for compatibility
LineItem = InvoiceLineItem


@dataclass
class InvoiceHeader:
    """Represents metadata and summary amounts extracted from invoice header."""
    invoice_number: str
    invoice_date: str
    vendor_name: str
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    total_due: Decimal
    vendor_tax_id: Optional[str] = None
    billing_address: Optional[str] = None
    purchase_order_number: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "vendor_name": self.vendor_name,
            "currency": self.currency,
            "subtotal": float(self.subtotal),
            "tax_amount": float(self.tax_amount),
            "total_due": float(self.total_due),
            "vendor_tax_id": self.vendor_tax_id,
            "billing_address": self.billing_address,
            "purchase_order_number": self.purchase_order_number,
        }


@dataclass
class AuditDiscrepancy:
    """Flags mathematical or structural reconciliation anomalies."""
    discrepancy_type: str
    field_name: str
    expected_value: Decimal
    actual_value: Decimal
    variance: Decimal
    severity: str = "WARNING"
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "discrepancy_type": self.discrepancy_type,
            "field_name": self.field_name,
            "expected_value": float(self.expected_value),
            "actual_value": float(self.actual_value),
            "variance": float(self.variance),
            "severity": self.severity,
            "notes": self.notes,
        }


@dataclass
class ExtractedInvoice:
    """Complete extracted invoice container with reconciliation mechanics."""
    invoice_number: str
    invoice_date: str
    vendor_name: str
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    total_due: Decimal
    line_items: List[InvoiceLineItem] = field(default_factory=list)
    confidence_score: float = 1.0
    extraction_source: str = "pdfplumber_layout"
    is_mathematically_valid: bool = False
    quarantine_reason: Optional[str] = None
    extracted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def verify_reconciliation(self) -> bool:
        """Verify sum of line items matches subtotal and subtotal + tax matches total_due."""
        if not self.line_items:
            self.is_mathematically_valid = False
            return False

        sum_items = sum((item.total_amount for item in self.line_items), Decimal("0.00"))
        subtotal_match = abs(sum_items - self.subtotal) <= Decimal("0.10")
        total_match = abs((self.subtotal + self.tax_amount) - self.total_due) <= Decimal("0.10")

        self.is_mathematically_valid = subtotal_match and total_match
        return self.is_mathematically_valid

    def get_audit_discrepancies(self) -> List[AuditDiscrepancy]:
        """Generate structured audit discrepancy records for any mathematical imbalance."""
        discrepancies: List[AuditDiscrepancy] = []
        if not self.line_items:
            discrepancies.append(
                AuditDiscrepancy(
                    discrepancy_type="EMPTY_LINE_ITEMS",
                    field_name="line_items",
                    expected_value=self.subtotal,
                    actual_value=Decimal("0.00"),
                    variance=self.subtotal,
                    severity="CRITICAL",
                    notes="Invoice contains zero extracted line items",
                )
            )
            return discrepancies

        sum_items = sum((item.total_amount for item in self.line_items), Decimal("0.00"))
        if abs(sum_items - self.subtotal) > Decimal("0.10"):
            discrepancies.append(
                AuditDiscrepancy(
                    discrepancy_type="SUBTOTAL_MISMATCH",
                    field_name="subtotal",
                    expected_value=sum_items,
                    actual_value=self.subtotal,
                    variance=abs(sum_items - self.subtotal),
                    severity="ERROR",
                    notes="Sum of line item totals does not reconcile with invoice subtotal",
                )
            )

        calc_total = self.subtotal + self.tax_amount
        if abs(calc_total - self.total_due) > Decimal("0.10"):
            discrepancies.append(
                AuditDiscrepancy(
                    discrepancy_type="TOTAL_DUE_MISMATCH",
                    field_name="total_due",
                    expected_value=calc_total,
                    actual_value=self.total_due,
                    variance=abs(calc_total - self.total_due),
                    severity="ERROR",
                    notes="Subtotal plus tax does not reconcile with total due",
                )
            )

        for idx, item in enumerate(self.line_items, 1):
            if not item.validate_math():
                calc_item_total = (item.quantity * item.unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                discrepancies.append(
                    AuditDiscrepancy(
                        discrepancy_type="LINE_ITEM_MATH_ERROR",
                        field_name=f"line_items[{idx}].total_amount",
                        expected_value=calc_item_total,
                        actual_value=item.total_amount,
                        variance=abs(calc_item_total - item.total_amount),
                        severity="WARNING",
                        notes=f"Item '{item.item_description}' line math mismatch",
                    )
                )

        return discrepancies

    def to_db_row(self) -> Dict[str, Any]:
        """Convert extracted invoice into database row dictionary."""
        row = asdict(self)
        row["subtotal"] = float(self.subtotal)
        row["tax_amount"] = float(self.tax_amount)
        row["total_due"] = float(self.total_due)
        row["line_items"] = [item.to_dict() for item in self.line_items]
        return row


@dataclass
class ExtractionResult:
    """Encapsulates the end-to-end outcome of an invoice extraction pass."""
    success: bool
    invoice: Optional[ExtractedInvoice] = None
    discrepancies: List[AuditDiscrepancy] = field(default_factory=list)
    execution_time_ms: float = 0.0
    pages_processed: int = 1
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "invoice": self.invoice.to_db_row() if self.invoice else None,
            "discrepancies": [d.to_dict() for d in self.discrepancies],
            "execution_time_ms": self.execution_time_ms,
            "pages_processed": self.pages_processed,
            "error_message": self.error_message,
        }
