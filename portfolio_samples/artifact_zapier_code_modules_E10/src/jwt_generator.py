"""Pure-Python cryptographic authentication helper generating HMAC-SHA256 tokens
for third-party private API integrations without C-dependency libraries.
Strict zero em dash policy enforced.
"""
import base64
import hashlib
import hmac
import json
import time
from typing import Dict, Any, Optional


class JWTGenerator:
    def __init__(self, secret_key: str, issuer: str = "zapier_breakout", default_ttl: int = 3600):
        self.secret_key = secret_key.encode("utf-8")
        self.issuer = issuer
        self.default_ttl = default_ttl

    @staticmethod
    def _base64url_encode(data: bytes) -> str:
        """Encode bytes using URL-safe Base64 without padding."""
        return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

    @staticmethod
    def _base64url_decode(data_str: str) -> bytes:
        """Decode URL-safe Base64 string with restored padding."""
        padded = data_str + "=" * ((4 - len(data_str) % 4) % 4)
        return base64.urlsafe_b64decode(padded.encode("utf-8"))

    def generate_token(self, subject: str, audience: str, custom_claims: Optional[Dict[str, Any]] = None, ttl_seconds: Optional[int] = None) -> str:
        """Generate a valid HMAC-SHA256 JWT token with standard claims."""
        now = int(time.time())
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl

        header = {
            "alg": "HS256",
            "typ": "JWT"
        }

        payload: Dict[str, Any] = {
            "iss": self.issuer,
            "sub": subject,
            "aud": audience,
            "iat": now,
            "nbf": now,
            "exp": now + ttl,
        }
        if custom_claims:
            payload.update(custom_claims)

        header_json = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

        header_b64 = self._base64url_encode(header_json)
        payload_b64 = self._base64url_encode(payload_json)

        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        signature = hmac.new(self.secret_key, signing_input, hashlib.sha256).digest()
        signature_b64 = self._base64url_encode(signature)

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    def verify_token(self, token: str, audience: Optional[str] = None) -> Dict[str, Any]:
        """Verify JWT signature, expiration, and claims. Returns payload if valid."""
        parts = token.strip().split(".")
        if len(parts) != 3:
            raise ValueError("Malformed token: expected 3 parts separated by dots")

        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(self.secret_key, signing_input, hashlib.sha256).digest()
        expected_sig_b64 = self._base64url_encode(expected_sig)

        # Constant-time comparison
        if not hmac.compare_digest(signature_b64, expected_sig_b64):
            raise ValueError("Invalid signature: signature verification failed")

        payload_bytes = self._base64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        now = int(time.time())
        if "exp" in payload and payload["exp"] < now:
            raise ValueError("Token expired")

        if "nbf" in payload and payload["nbf"] > now:
            raise ValueError("Token not yet active")

        if audience and payload.get("aud") != audience:
            raise ValueError(f"Audience mismatch: expected {audience}, got {payload.get('aud')}")

        return payload
