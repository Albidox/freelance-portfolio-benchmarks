"""System configuration and environment parameters for Payment Reconciliation.
Zero em dashes policy strictly enforced.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentReconcilerConfig:
    db_host: str = os.getenv("PGHOST", "127.0.0.1")
    db_port: int = int(os.getenv("PGPORT", "5433"))
    db_user: str = os.getenv("PGUSER", "postgres")
    db_password: str = os.getenv("PGPASSWORD", "postgres")
    db_name: str = os.getenv("PGDATABASE", "postgres")
    db_schema: str = os.getenv("PGSCHEMA", "e5_reconciliation")

    stripe_webhook_secret: str = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret_1234567890abcdef")
    razorpay_webhook_secret: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "rzp_secret_9876543210fedcba")

    replay_tolerance_seconds: int = int(os.getenv("REPLAY_TOLERANCE", "300"))
    max_memory_mb: int = int(os.getenv("MAX_MEMORY_MB", "250"))
    batch_drain_limit: int = int(os.getenv("BATCH_DRAIN_LIMIT", "500"))
    max_retry_attempts: int = int(os.getenv("MAX_RETRY_ATTEMPTS", "5"))
