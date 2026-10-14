"""Dynamic request signer computing anti-tamper mobile headers.
Strict zero em dash policy enforced.
"""
import hmac
import hashlib
import uuid
import time
from typing import Dict, Any, Tuple
from src.models import ApiSignatureRequest, DeviceFingerprint


class MobileRequestSigner:
    def __init__(self, api_secret: str, salt_prefix: str = "SALT_V2"):
        self.api_secret = api_secret
        self.salt_prefix = salt_prefix

    def generate_nonce(self) -> str:
        """Generate cryptographically secure 16-character hexadecimal nonce."""
        return uuid.uuid4().hex[:16]

    def compute_signature(self, request_data: ApiSignatureRequest) -> str:
        """Calculate HMAC-SHA256 signature over canonicalized request string."""
        canonical_str = request_data.to_canonical_string()
        key_material = f"{self.salt_prefix}_{self.api_secret}".encode("utf-8")
        computed_hmac = hmac.new(
            key_material,
            canonical_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return computed_hmac

    def build_signed_headers(
        self,
        method: str,
        path: str,
        payload_body: str,
        device: DeviceFingerprint
    ) -> Dict[str, str]:
        """Assemble complete header package including device fingerprint and signature."""
        now_epoch = int(time.time())
        nonce = self.generate_nonce()
        
        req = ApiSignatureRequest(
            method=method,
            endpoint_path=path,
            timestamp_epoch=now_epoch,
            nonce=nonce,
            payload_body=payload_body,
            api_secret=self.api_secret
        )
        sig = self.compute_signature(req)

        headers = device.to_headers()
        headers.update({
            "X-Signature": sig,
            "X-Timestamp": str(now_epoch),
            "X-Nonce": nonce,
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        return headers

    def verify_signature(self, request_data: ApiSignatureRequest, signature_to_verify: str) -> bool:
        """Verify incoming signature against expected calculation using constant-time comparison."""
        expected = self.compute_signature(request_data)
        return hmac.compare_digest(expected, signature_to_verify)
