"""Standalone zero-dependency HMAC-SHA256 signature generator for outbound webhooks.
Strict zero em dash policy enforced.
"""
import hmac
import hashlib
import json
import time
from typing import Dict, Any, Union, Optional, Tuple


class CryptoSigner:
    """Production cryptographic webhook signer using HMAC-SHA256 with timing-safe verification."""

    def __init__(self, default_secret: str = "default_secret_key"):
        self.default_secret = default_secret

    @staticmethod
    def _to_bytes(data: Union[str, bytes, Dict[str, Any]]) -> bytes:
        """Convert arbitrary payload into deterministic bytes."""
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        if isinstance(data, dict):
            return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return str(data).encode("utf-8")

    def sign_payload(
        self,
        payload: Union[str, bytes, Dict[str, Any]],
        secret: Optional[str] = None,
        digest_format: str = "hex"
    ) -> str:
        """Generate HMAC-SHA256 signature of the payload."""
        key = (secret or self.default_secret).encode("utf-8")
        data_bytes = self._to_bytes(payload)
        sig = hmac.new(key, data_bytes, hashlib.sha256)
        if digest_format == "base64":
            import base64
            return base64.b64encode(sig.digest()).decode("utf-8")
        return sig.hexdigest()

    def verify_signature(
        self,
        payload: Union[str, bytes, Dict[str, Any]],
        signature: str,
        secret: Optional[str] = None,
        digest_format: str = "hex"
    ) -> bool:
        """Verify HMAC-SHA256 signature using constant-time comparison to prevent timing attacks."""
        expected_sig = self.sign_payload(payload, secret=secret, digest_format=digest_format)
        clean_sig = signature.strip()
        # Handle prefix like 'sha256='
        if clean_sig.startswith("sha256="):
            clean_sig = clean_sig[7:]
        return hmac.compare_digest(expected_sig, clean_sig)

    def generate_webhook_headers(
        self,
        payload: Union[str, bytes, Dict[str, Any]],
        secret: Optional[str] = None,
        timestamp: Optional[int] = None,
        header_prefix: str = "X-Webhook-"
    ) -> Dict[str, str]:
        """Generate complete outbound webhook security headers including timestamp and signature."""
        ts = timestamp if timestamp is not None else int(time.time())
        data_bytes = self._to_bytes(payload)
        signed_body = f"{ts}.".encode("utf-8") + data_bytes
        sig = self.sign_payload(signed_body, secret=secret, digest_format="hex")
        return {
            f"{header_prefix}Timestamp": str(ts),
            f"{header_prefix}Signature": f"sha256={sig}",
            f"{header_prefix}Algorithm": "HMAC-SHA256",
            "Content-Type": "application/json"
        }

    def verify_webhook_request(
        self,
        headers: Dict[str, str],
        raw_body: Union[str, bytes],
        secret: Optional[str] = None,
        max_drift_seconds: int = 300,
        header_prefix: str = "X-Webhook-"
    ) -> Tuple[bool, str]:
        """Verify incoming webhook request headers, timestamp freshness, and signature."""
        # Find headers case-insensitively
        norm_headers = {k.lower(): v for k, v in headers.items()}
        ts_key = f"{header_prefix}Timestamp".lower()
        sig_key = f"{header_prefix}Signature".lower()

        if ts_key not in norm_headers or sig_key not in norm_headers:
            return False, "Missing required security headers"

        try:
            ts = int(norm_headers[ts_key])
        except ValueError:
            return False, "Invalid timestamp header"

        now = int(time.time())
        if abs(now - ts) > max_drift_seconds:
            return False, f"Timestamp drift {abs(now - ts)}s exceeded max tolerance {max_drift_seconds}s"

        body_bytes = self._to_bytes(raw_body)
        signed_body = f"{ts}.".encode("utf-8") + body_bytes
        raw_sig = norm_headers[sig_key]
        if not self.verify_signature(signed_body, raw_sig, secret=secret, digest_format="hex"):
            return False, "Invalid cryptographic signature"

        return True, "Valid signature and timestamp"
