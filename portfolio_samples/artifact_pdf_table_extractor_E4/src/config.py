"""System configuration and environment parameters for PDF Extractor.
Strict zero em dash policy enforced.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractorConfig:
    db_host: str = os.getenv("PGHOST", "127.0.0.1")
    db_port: int = int(os.getenv("PGPORT", "5433"))
    db_user: str = os.getenv("PGUSER", "postgres")
    db_password: str = os.getenv("PGPASSWORD", "postgres")
    db_name: str = os.getenv("PGDATABASE", "postgres")
    db_schema: str = os.getenv("PGSCHEMA", "e4_pdf_extractor")

    sqlite_audit_path: str = os.getenv("SQLITE_AUDIT_PATH", "extraction_audit.db")
    max_memory_mb: int = int(os.getenv("MAX_MEMORY_MB", "250"))
    page_timeout_seconds: float = float(os.getenv("PAGE_TIMEOUT", "10.0"))
    min_confidence_threshold: float = float(os.getenv("MIN_CONFIDENCE", "0.85"))
    enable_ocr_fallback: bool = os.getenv("ENABLE_OCR_FALLBACK", "true").lower() == "true"
