"""
sanitizer_schema.py: Production Pydantic v2 schema for dirty record sanitization.
Enforces Decimal precision, multi-format timestamp coercion, and email validation.
Strict constraint: Zero em dashes.
"""

from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import math
import re
from typing import Any, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict

# Precompiled regex patterns for high-throughput validation
RE_EMAIL = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$")
RE_DATE_SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
CURRENCY_STRIP_MAP = {ord(c): None for c in "$€£¥,"}
Q_CENT = Decimal("0.01")
ZERO_DECIMAL = Decimal("0.00")
MAX_AMOUNT = Decimal("9999999999.99")
UTC = timezone.utc

class SanitizedTransaction(BaseModel):
    """
    Sanitized financial transaction record.
    Coerces raw dirty strings into strict, typed, validated domain objects.
    """
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )

    record_id: int = Field(..., ge=0, description="Unique record index")
    client_id: str = Field(..., min_length=1, max_length=64, description="Sanitized client identifier")
    amount: Decimal = Field(..., ge=ZERO_DECIMAL, le=MAX_AMOUNT, description="Coerced transaction amount with 2 decimal places")
    timestamp: datetime = Field(..., description="Normalized UTC ISO 8601 timestamp")
    email: str = Field(..., min_length=3, max_length=320, description="Validated lowercase email address")
    status: str = Field(default="active", min_length=1, max_length=32, description="Normalized transaction status")

    @field_validator("amount", mode="before")
    @classmethod
    def sanitize_amount(cls, v: Any) -> Decimal:
        """
        Coerces multi-format currency strings, symbols, and labels into exact Decimal precision.
        Rejects negative amounts, nulls, NaNs, infinities, and non-numeric garbage.
        """
        if v is None:
            raise ValueError("Amount field cannot be null")

        if isinstance(v, (int, float, Decimal)):
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                raise ValueError(f"Amount cannot be NaN or Infinite: {v}")

            try:
                d = Decimal(str(v))
            except (InvalidOperation, ValueError) as err:
                raise ValueError(f"Invalid numeric amount: {v}") from err

            if not d.is_finite():
                raise ValueError(f"Amount cannot be NaN or Infinite: {v}")

            if d < ZERO_DECIMAL:
                raise ValueError(f"Amount cannot be negative: {v}")

            if d > MAX_AMOUNT:
                raise ValueError(f"Amount exceeds maximum allowed limit: {v}")

            try:
                return d.quantize(Q_CENT)
            except InvalidOperation as err:
                raise ValueError(f"Cannot quantize amount to cents: {v}") from err

        if isinstance(v, str):
            if len(v) > 1024:
                raise ValueError(f"Amount string length exceeds maximum allowable limit: {len(v)}")

            s = v.strip().upper()
            if not s:
                raise ValueError("Amount cannot be an empty string")

            if s in ("NAN", "INF", "INFINITY", "-INF", "-INFINITY", "+INF", "+INFINITY"):
                raise ValueError(f"Amount cannot be NaN or Infinite: {v}")

            if s == "FREE":
                return ZERO_DECIMAL

            # Strip currency code suffixes and prefixes
            for suffix in (" USD", " EUR", " GBP", " JPY", " CAD", " AUD"):
                if s.endswith(suffix):
                    s = s[:-len(suffix)].strip()
            for prefix in ("USD ", "EUR ", "GBP ", "JPY ", "CAD ", "AUD "):
                if s.startswith(prefix):
                    s = s[len(prefix):].strip()

            # Strip currency symbols and thousands separators
            s = s.translate(CURRENCY_STRIP_MAP).strip()
            if not s:
                raise ValueError("Amount string contains no digits after stripping symbols")

            if s.startswith("-"):
                raise ValueError(f"Amount cannot be negative: {v}")

            # Verify first character is digit or decimal point
            if not (s[0].isdigit() or s[0] == "."):
                raise ValueError(f"Unparseable currency string: {v}")

            try:
                d = Decimal(s)
            except (InvalidOperation, ValueError):
                raise ValueError(f"Invalid decimal literal: {v}")

            if not d.is_finite():
                raise ValueError(f"Amount cannot be NaN or Infinite: {v}")

            if d < ZERO_DECIMAL:
                raise ValueError(f"Amount cannot be negative: {v}")

            if d > MAX_AMOUNT:
                raise ValueError(f"Amount exceeds maximum allowed limit: {v}")

            try:
                return d.quantize(Q_CENT)
            except InvalidOperation:
                raise ValueError(f"Cannot quantize amount to cents: {v}")

        raise ValueError(f"Unsupported amount type: {type(v).__name__}")

    @field_validator("timestamp", mode="before")
    @classmethod
    def sanitize_timestamp(cls, v: Any) -> datetime:
        """
        Coerces multi-format date strings into normalized UTC datetime objects.
        Supports ISO 8601, MM/DD/YYYY, and Unix epoch timestamps.
        Rejects broken dates, invalid dates, and nulls.
        """
        if v is None:
            raise ValueError("Timestamp field cannot be null")

        if isinstance(v, datetime):
            return v.astimezone(UTC) if v.tzinfo else v.replace(tzinfo=UTC)

        if isinstance(v, (int, float)):
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                raise ValueError(f"Timestamp cannot be NaN or Infinite: {v}")

            # Unix epoch timestamp
            if v < 0 or v > 4102444800: # Year 1970 to 2100 bounds
                raise ValueError(f"Epoch timestamp out of valid bounds: {v}")
            try:
                return datetime.fromtimestamp(v, tz=UTC)
            except (ValueError, OverflowError, OSError) as err:
                raise ValueError(f"Invalid epoch timestamp: {v}") from err

        if isinstance(v, str):
            if len(v) > 256:
                raise ValueError(f"Timestamp string length exceeds maximum allowable limit: {len(v)}")

            s = v.strip()
            if not s:
                raise ValueError("Timestamp cannot be an empty string")

            # Fast path: numeric starting char
            if s[0].isdigit():
                # Format: YYYY-MM-DD
                if len(s) == 10 and s[4] == "-" and s[7] == "-":
                    try:
                        return datetime(int(s[0:4]), int(s[5:7]), int(s[8:10]), tzinfo=UTC)
                    except (ValueError, OverflowError):
                        raise ValueError(f"Invalid date values: {v}")

                # Format: MM/DD/YYYY
                if len(s) == 10 and s[2] == "/" and s[5] == "/":
                    try:
                        m, d, y = int(s[0:2]), int(s[3:5]), int(s[6:10])
                        return datetime(y, m, d, tzinfo=UTC)
                    except (ValueError, OverflowError):
                        raise ValueError(f"Invalid date values: {v}")

                # Format: YYYY/MM/DD
                if len(s) == 10 and s[4] == "/" and s[7] == "/":
                    try:
                        y, m, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
                        return datetime(y, m, d, tzinfo=UTC)
                    except (ValueError, OverflowError):
                        raise ValueError(f"Invalid date values: {v}")

                # Full ISO 8601 datetime with time and timezone
                try:
                    dt = datetime.fromisoformat(s)
                    return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
                except (ValueError, OverflowError):
                    raise ValueError(f"Unparseable ISO 8601 timestamp: {v}")

            raise ValueError(f"Unsupported timestamp format: {v}")

        raise ValueError(f"Unsupported timestamp type: {type(v).__name__}")

    @field_validator("email", mode="before")
    @classmethod
    def sanitize_email(cls, v: Any) -> str:
        """
        Validates email syntax, lowercases domain, and rejects malformed addresses.
        """
        if v is None:
            raise ValueError("Email field cannot be null")

        if not isinstance(v, str):
            raise ValueError(f"Email must be a string, got {type(v).__name__}")

        if len(v) > 320:
            raise ValueError(f"Email length exceeds 320 characters: {len(v)}")

        s = v.strip().lower()
        if not s:
            raise ValueError("Email cannot be an empty string")

        if "@" not in s or "." not in s:
            raise ValueError(f"Invalid email syntax, missing at or dot: {v}")

        if not RE_EMAIL.match(s):
            raise ValueError(f"Invalid email syntax format: {v}")

        return s

    @field_validator("status", mode="before")
    @classmethod
    def sanitize_status(cls, v: Any) -> str:
        """
        Normalizes status string to lowercase.
        """
        if v is None:
            return "active"
        if isinstance(v, str):
            if len(v) > 64:
                raise ValueError(f"Status length exceeds 64 characters: {len(v)}")
            s = v.strip().lower()
            return s if s else "active"
        return str(v).lower()
