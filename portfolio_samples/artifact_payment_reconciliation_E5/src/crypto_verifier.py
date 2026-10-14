"""Cryptographic HMAC-SHA256 signature verifier and anti-replay guard for Stripe and Razorpay.
Zero em dashes policy strictly enforced.
"""
import hmac
import hashlib
import time
from typing import Tuple, Optional
from src.models import GatewayType
from src.config import PaymentReconcilerConfig


class WebhookSignatureVerifier:
    """Verifies cryptographic authenticity of incoming webhook payloads."""

    def __init__(self, config: PaymentReconcilerConfig):
        self.config = config
        self.replay_attacks_detected: int = 0
        self.tampered_signatures_detected: int = 0

    def verify_stripe_signature(
        self, payload: str, sig_header: str, current_time: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Verify Stripe v1 HMAC-SHA256 signature with timestamp replay check."""
        if not sig_header or not payload:
            self.tampered_signatures_detected += 1
            return False, "Missing signature or payload"

        now = current_time if current_time is not None else time.time()
        elements = sig_header.split(",")
        timestamp: Optional[int] = None
        signatures: list[str] = []

        for item in elements:
            parts = item.strip().split("=", 1)
            if len(parts) == 2:
                k, v = parts[0].strip(), parts[1].strip()
                if k == "t":
                    try:
                        timestamp = int(v)
                    except ValueError:
                        return False, "Malformed timestamp"
                elif k == "v1":
                    signatures.append(v)

        if timestamp is None or not signatures:
            self.tampered_signatures_detected += 1
            return False, "Malformed signature header components"

        # Anti-replay check: prevent events older than tolerance or drifting into future
        if (now - timestamp) > self.config.replay_tolerance_seconds:
            self.replay_attacks_detected += 1
            return False, f"Signature timestamp expired (older than {self.config.replay_tolerance_seconds}s)"
        if (timestamp - now) > 10:
            self.replay_attacks_detected += 1
            return False, "Signature timestamp too far in future"

        signed_payload = f"{timestamp}.{payload}".encode("utf-8")
        secret_bytes = self.config.stripe_webhook_secret.encode("utf-8")
        expected_sig = hmac.new(secret_bytes, signed_payload, hashlib.sha256).hexdigest()

        for sig in signatures:
            if hmac.compare_digest(expected_sig, sig):
                return True, "Valid signature"

        self.tampered_signatures_detected += 1
        return False, "Signature mismatch"

    def verify_razorpay_signature(self, payload: str, signature: str) -> Tuple[bool, str]:
        """Verify Razorpay HMAC-SHA256 signature using constant-time comparison."""
        if not signature or not payload:
            self.tampered_signatures_detected += 1
            return False, "Missing signature or payload"

        secret_bytes = self.config.razorpay_webhook_secret.encode("utf-8")
        expected_sig = hmac.new(secret_bytes, payload.encode("utf-8"), hashlib.sha256).hexdigest()

        if hmac.compare_digest(expected_sig, signature):
            return True, "Valid signature"

        self.tampered_signatures_detected += 1
        return False, "Razorpay signature mismatch"


# Canonical alias for cryptographic verifier
CryptoSignatureVerifier = WebhookSignatureVerifier
