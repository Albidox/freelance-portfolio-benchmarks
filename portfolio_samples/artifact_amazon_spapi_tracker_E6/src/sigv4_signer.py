"""AWS Signature Version 4 (SigV4) HMAC-SHA256 request signing engine."""

import hmac
import hashlib
import time
from typing import Dict, Any, Optional
from urllib.parse import quote


class SigV4Signer:
    """Computes AWS Signature Version 4 HMAC-SHA256 headers for Amazon SP-API requests."""

    def __init__(self, aws_access_key: str, aws_secret_key: str, aws_region: str = "us-east-1"):
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.aws_region = aws_region

    def derive_signing_key(self, date_stamp: str, service: str) -> bytes:
        """Derive cryptographic key hierarchy: kDate -> kRegion -> kService -> kSigning."""
        k_date = hmac.new(
            f"AWS4{self.aws_secret_key}".encode("utf-8"),
            date_stamp.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        k_region = hmac.new(k_date, self.aws_region.encode("utf-8"), hashlib.sha256).digest()
        k_service = hmac.new(k_region, service.encode("utf-8"), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()
        return k_signing

    def compute_canonical_request(
        self,
        method: str,
        canonical_uri: str,
        query_params: Dict[str, str],
        canonical_headers: str,
        signed_headers: str,
        payload_hash: str,
    ) -> str:
        """Format canonical request according to AWS SigV4 specification."""
        canonical_querystring = "&".join(
            f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted(query_params.items())
        )
        return (
            f"{method}\n"
            f"{canonical_uri}\n"
            f"{canonical_querystring}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{payload_hash}"
        )

    def sign(
        self,
        method: str,
        service: str,
        host: str,
        canonical_uri: str,
        query_params: Dict[str, str],
        payload: str = "",
        timestamp_epoch: Optional[float] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, str]:
        """Generate complete AWS SigV4 signed headers for SP-API."""
        now = timestamp_epoch if timestamp_epoch is not None else time.time()
        amz_date = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now))
        date_stamp = time.strftime("%Y%m%d", time.gmtime(now))

        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_headers = f"host:{host}\nx-amz-date:{amz_date}\n"
        signed_headers = "host;x-amz-date"

        canonical_request = self.compute_canonical_request(
            method=method,
            canonical_uri=canonical_uri,
            query_params=query_params,
            canonical_headers=canonical_headers,
            signed_headers=signed_headers,
            payload_hash=payload_hash,
        )

        credential_scope = f"{date_stamp}/{self.aws_region}/{service}/aws4_request"
        canonical_req_hash = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n{canonical_req_hash}"

        signing_key = self.derive_signing_key(date_stamp, service)
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        auth_header = (
            f"AWS4-HMAC-SHA256 Credential={self.aws_access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        headers = {
            "host": host,
            "x-amz-date": amz_date,
            "Authorization": auth_header,
        }
        if access_token:
            headers["x-amz-access-token"] = access_token
        return headers
