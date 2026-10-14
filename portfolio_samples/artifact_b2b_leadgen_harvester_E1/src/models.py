"""Data models and validation contracts for B2B Lead Harvester.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
import re
from datetime import datetime, timezone

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^\+?[0-9\s\-\(\)\.]{7,25}$")


class VerificationStatus(str, Enum):
    DELIVERABLE = "DELIVERABLE"
    UNDELIVERABLE = "UNDELIVERABLE"
    DISPOSABLE = "DISPOSABLE"
    RISKY = "RISKY"
    SYNTAX_INVALID = "SYNTAX_INVALID"
    UNVERIFIED = "UNVERIFIED"


@dataclass
class CompanyTarget:
    name: str
    url: str
    industry: Optional[str] = None
    location: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class LeadRecord:
    company_name: str
    source_url: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    industry: Optional[str] = None
    status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence_score: float = 0.0
    extracted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RawLeadRecord:
    company_name: str
    source_url: str
    raw_email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    industry: Optional[str] = None
    extracted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class VerifiedLead:
    company_name: str
    domain: str
    email: str
    is_deliverable: bool
    mx_records: List[str]
    smtp_check_passed: bool
    phone: Optional[str]
    address: Optional[str]
    contact_name: Optional[str]
    industry: Optional[str]
    source_url: str
    confidence_score: float
    verification_latency_ms: float
    verified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_db_row(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def validate_email_syntax(cls, email: str) -> bool:
        if not email or len(email) > 254:
            return False
        return bool(EMAIL_REGEX.match(email.strip()))

    @classmethod
    def clean_phone(cls, phone: Optional[str]) -> Optional[str]:
        if not phone:
            return None
        cleaned = re.sub(r"[^\d+]", "", phone.strip())
        return cleaned if len(cleaned) >= 7 else None
