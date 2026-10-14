"""AWS SigV4 request signer, LWA OAuth2 token manager, and rate-limited client."""

import hmac
import hashlib
import time
from typing import Dict, Any, Optional
from urllib.parse import quote
from src.config import SPAPIConfig
from src.sigv4_signer import SigV4Signer
from src.lwa_auth import LWAAuthEngine


class AmazonSPAPIClient:
    """Handles LWA token exchange and cryptographic AWS SigV4 request signing."""

    def __init__(self, config: SPAPIConfig):
        self.config = config
        self._auth_engine = LWAAuthEngine(config, token_lifetime_seconds=3600, refresh_window_seconds=300)
        self._signer = SigV4Signer(
            aws_access_key=config.aws_access_key,
            aws_secret_key=config.aws_secret_key,
            aws_region=config.aws_region,
        )
        self.rate_limit_throttle_count: int = 0

    @property
    def lwa_refresh_count(self) -> int:
        return self._auth_engine.refresh_count

    @lwa_refresh_count.setter
    def lwa_refresh_count(self, value: int) -> None:
        self._auth_engine.refresh_count = value

    def get_valid_lwa_token(self, current_time: Optional[float] = None) -> str:
        """Return valid LWA access token, refreshing if expiring within 300 seconds."""
        return self._auth_engine.get_valid_token(current_time=current_time)

    def compute_sigv4_headers(
        self,
        method: str,
        service: str,
        host: str,
        canonical_uri: str,
        query_params: Dict[str, str],
        payload: str,
        timestamp_epoch: Optional[float] = None,
    ) -> Dict[str, str]:
        """Compute AWS Signature Version 4 headers for SP-API calls."""
        now = timestamp_epoch if timestamp_epoch is not None else time.time()
        token = self.get_valid_lwa_token(now)
        return self._signer.sign(
            method=method,
            service=service,
            host=host,
            canonical_uri=canonical_uri,
            query_params=query_params,
            payload=payload,
            timestamp_epoch=now,
            access_token=token,
        )

    def calculate_leaky_bucket_backoff(
        self,
        attempt: int,
        base_seconds: float = 1.0,
        max_seconds: float = 30.0,
    ) -> float:
        """Exponential backoff with jitter for SP-API quota limits (HTTP 429)."""
        self.rate_limit_throttle_count += 1
        delay = min(max_seconds, base_seconds * (2 ** (attempt - 1)))
        return round(delay, 2)
