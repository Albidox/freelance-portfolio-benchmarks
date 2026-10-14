"""Normalizer for currencies, ISO dates, tax balancing, and OCR error recovery.
Strict zero em dash policy enforced.
"""
import re
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple


class InvoiceDataCleaner:
    """Normalizes unstructured invoice header data into standardized formats."""

    CURRENCY_SYMBOLS: Dict[str, str] = {
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
        "₹": "INR",
        "¥": "JPY",
    }

    DATE_PATTERNS = [
        r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})",       # YYYY-MM-DD
        r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})",       # DD-MM-YYYY or MM-DD-YYYY
        r"([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})",   # Month DD, YYYY
    ]

    OCR_NUMERIC_TRANSLATIONS = str.maketrans({
        "O": "0",
        "o": "0",
        "I": "1",
        "l": "1",
        "S": "5",
        "s": "5",
        "B": "8",
    })

    def normalize_currency(self, text: str) -> str:
        """Detect currency symbol or code and return standard ISO code."""
        if not text:
            return "USD"
        for symbol, code in self.CURRENCY_SYMBOLS.items():
            if symbol in text:
                return code
        match = re.search(r"\b(USD|EUR|GBP|INR|CAD|AUD)\b", text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return "USD"

    def normalize_date(self, text: str) -> Optional[str]:
        """Convert unstructured date string to ISO-8601 YYYY-MM-DD."""
        if not text:
            return None

        # Test explicit formats
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y", "%b %d, %Y"):
            try:
                dt = datetime.strptime(text.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        # Regex fallback for YYYY-MM-DD
        match = re.search(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", text)
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"

        return None

    def sanitize_text(self, text: Optional[str]) -> str:
        """Strip control characters, non-printable noise, and double spaces."""
        if not text:
            return ""
        # Remove ASCII control characters except standard whitespace
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def clean_monetary_amount(self, val: str) -> Decimal:
        """Extract exact Decimal amount from raw string with currency artifacts."""
        if not val:
            return Decimal("0.00")
        cleaned = re.sub(r"[^0-9.,-]", "", val)
        if not cleaned:
            return Decimal("0.00")
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        try:
            return Decimal(cleaned).quantize(Decimal("0.01"))
        except Exception:
            return Decimal("0.00")

    def recover_ocr_numeric(self, raw_num_str: str) -> Decimal:
        """Recover common OCR character misrecognitions in numeric fields."""
        if not raw_num_str:
            return Decimal("0.00")
        # Apply character translations
        translated = raw_num_str.translate(self.OCR_NUMERIC_TRANSLATIONS)
        return self.clean_monetary_amount(translated)

    def verify_tax_balancing(
        self,
        subtotal: Decimal,
        tax_amount: Decimal,
        total_due: Decimal,
        tolerance: Decimal = Decimal("0.10"),
    ) -> bool:
        """Verify whether subtotal + tax_amount equals total_due within tolerance."""
        calculated = subtotal + tax_amount
        return abs(calculated - total_due) <= tolerance


# Direct alias for component naming parity
InvoiceNormalizer = InvoiceDataCleaner
