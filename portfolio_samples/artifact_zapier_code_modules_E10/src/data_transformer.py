"""Lightweight transformation module parsing nested JSON structures, date normalization,
and currency calculations within serverless memory constraints.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional
import re
from datetime import datetime, timezone


class DataTransformer:
    def __init__(self):
        self.transformations_count = 0

    def flatten_dict(self, d: Dict[str, Any], parent_key: str = "", sep: str = "_") -> Dict[str, Any]:
        """Flatten deeply nested dictionary into single-level key-value pairs."""
        items: List[tuple] = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
            if isinstance(v, dict):
                items.extend(self.flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                for idx, item in enumerate(v):
                    list_key = f"{new_key}{sep}{idx}"
                    if isinstance(item, dict):
                        items.extend(self.flatten_dict(item, list_key, sep=sep).items())
                    else:
                        items.append((list_key, item))
            else:
                items.append((new_key, v))
        self.transformations_count += 1
        return dict(items)

    def normalize_keys(self, input_dict: Dict[str, Any], case_style: str = "snake") -> Dict[str, Any]:
        """Convert arbitrary dictionary keys (camelCase, PascalCase, kebab-case) to snake_case."""
        normalized: Dict[str, Any] = {}
        for k, v in input_dict.items():
            clean_k = str(k).strip()
            # Replace spaces and hyphens with underscores
            clean_k = re.sub(r"[\s\-]+", "_", clean_k)
            # Insert underscore between camelCase boundaries
            clean_k = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", clean_k)
            # Remove non-alphanumeric except underscores
            clean_k = re.sub(r"[^a-zA-Z0-9_]", "", clean_k).lower()

            if isinstance(v, dict):
                normalized[clean_k] = self.normalize_keys(v, case_style=case_style)
            elif isinstance(v, list):
                normalized[clean_k] = [
                    self.normalize_keys(item, case_style=case_style) if isinstance(item, dict) else item
                    for item in v
                ]
            else:
                normalized[clean_k] = v
        self.transformations_count += 1
        return normalized

    def extract_nested_fields(self, data: Dict[str, Any], field_paths: Dict[str, str], defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract dot-notated nested fields safely with fallback defaults."""
        defaults = defaults or {}
        extracted: Dict[str, Any] = {}
        for target_key, path in field_paths.items():
            parts = path.split(".")
            curr: Any = data
            found = True
            for part in parts:
                if isinstance(curr, dict) and part in curr:
                    curr = curr[part]
                else:
                    found = False
                    break
            extracted[target_key] = curr if found else defaults.get(target_key, None)
        return extracted

    def convert_currency(self, amount: float, source_currency: str, target_currency: str, rate_table: Dict[str, float]) -> float:
        """Convert monetary amounts using a fixed exchange rate table with rounding."""
        src = source_currency.upper().strip()
        tgt = target_currency.upper().strip()
        if src == tgt:
            return round(amount, 2)

        rate_key = f"{src}_{tgt}"
        if rate_key in rate_table:
            return round(amount * rate_table[rate_key], 2)

        # Check reciprocal
        reciprocal_key = f"{tgt}_{src}"
        if reciprocal_key in rate_table and rate_table[reciprocal_key] > 0:
            return round(amount / rate_table[reciprocal_key], 2)

        raise ValueError(f"Conversion rate not found for pair {src} to {tgt}")

    def parse_datetime_iso(self, date_str: str, output_format: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Parse various date formats into standardized ISO formatted strings."""
        clean_str = str(date_str).strip()
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(clean_str, fmt)
                return dt.strftime(output_format)
            except ValueError:
                continue
        # Fallback to current UTC timestamp if unparseable
        return datetime.now(timezone.utc).strftime(output_format)
