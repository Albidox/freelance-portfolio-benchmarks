"""Direct async API caller using httpx with token rotation and rate limit handling.
Strict zero em dash policy enforced.
"""
import asyncio
import time
import json
from typing import Dict, Any, List, Optional, Tuple
import httpx
from src.models import ReplayResponse, BearerToken, DevicePlatform
from src.header_impersonator import HeaderImpersonator


class ApiReplayEngine:
    """Executes high-throughput asynchronous and synchronous API replays with token rotation."""

    def __init__(
        self,
        base_url: str = "https://api.internal-target.com",
        tokens: Optional[List[str]] = None,
        max_retries: int = 3,
        base_backoff: float = 0.5,
        impersonator: Optional[HeaderImpersonator] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.tokens: List[str] = tokens or ["token_alpha_1", "token_beta_2", "token_gamma_3"]
        self.current_token_idx: int = 0
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.impersonator = impersonator or HeaderImpersonator(DevicePlatform.ANDROID)
        self.rotation_count = 0
        self.total_replays = 0
        self.rate_limits_handled = 0

    def get_current_token(self) -> str:
        """Get the active bearer token from the rotation pool."""
        if not self.tokens:
            return ""
        return self.tokens[self.current_token_idx % len(self.tokens)]

    def rotate_token(self) -> str:
        """Rotate to next token in pool upon 401 or token expiration."""
        if not self.tokens:
            return ""
        self.current_token_idx = (self.current_token_idx + 1) % len(self.tokens)
        self.rotation_count += 1
        return self.get_current_token()

    def add_token(self, token: str) -> None:
        """Add new token to rotation pool."""
        if token and token not in self.tokens:
            self.tokens.append(token)

    async def replay_request_async(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        mock_response: Optional[Tuple[int, Dict[str, Any]]] = None
    ) -> ReplayResponse:
        """Execute async API replay using httpx with automatic token rotation and rate limit backoff."""
        self.total_replays += 1
        full_url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        host = self.base_url.replace("https://", "").replace("http://", "").split("/")[0]

        headers = self.impersonator.generate_headers(
            target_host=host,
            bearer_token=self.get_current_token()
        )
        if custom_headers:
            headers.update(custom_headers)

        # Support mock response for deterministic offline testing and benchmarking
        if mock_response is not None:
            status_code, body_dict = mock_response
            latency = 1.25
            if status_code == 401:
                self.rotate_token()
                return ReplayResponse(
                    endpoint=path,
                    status_code=401,
                    headers=headers,
                    raw_text=json.dumps(body_dict),
                    body_json=body_dict,
                    latency_ms=latency,
                    success=False,
                    error_message="Unauthorized: Token expired or rejected"
                )
            elif status_code == 429:
                self.rate_limits_handled += 1
                return ReplayResponse(
                    endpoint=path,
                    status_code=429,
                    headers=headers,
                    raw_text=json.dumps(body_dict),
                    body_json=body_dict,
                    latency_ms=latency,
                    success=False,
                    error_message="Rate limit exceeded"
                )
            return ReplayResponse(
                endpoint=path,
                status_code=status_code,
                headers=headers,
                raw_text=json.dumps(body_dict),
                body_json=body_dict,
                latency_ms=latency,
                success=True
            )

        # Live network execution with httpx
        attempt = 0
        last_error = None
        while attempt < self.max_retries:
            t0 = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    resp = await client.request(
                        method=method,
                        url=full_url,
                        params=params,
                        json=json_body,
                        headers=headers
                    )
                    t_latency = (time.perf_counter() - t0) * 1000.0

                    if resp.status_code == 401:
                        self.rotate_token()
                        headers["Authorization"] = f"Bearer {self.get_current_token()}"
                        attempt += 1
                        continue

                    if resp.status_code == 429:
                        self.rate_limits_handled += 1
                        retry_after = float(resp.headers.get("Retry-After", self.base_backoff * (2 ** attempt)))
                        await asyncio.sleep(min(retry_after, 2.0))
                        attempt += 1
                        continue

                    try:
                        parsed_json = resp.json()
                    except Exception:
                        parsed_json = None

                    return ReplayResponse(
                        endpoint=path,
                        status_code=resp.status_code,
                        headers=dict(resp.headers),
                        raw_text=resp.text,
                        body_json=parsed_json,
                        latency_ms=round(t_latency, 2),
                        success=resp.is_success,
                        error_message=None if resp.is_success else f"HTTP {resp.status_code}"
                    )
            except Exception as e:
                last_error = str(e)
                attempt += 1
                await asyncio.sleep(0.1)

        return ReplayResponse(
            endpoint=path,
            status_code=0,
            headers=headers,
            raw_text="",
            body_json=None,
            latency_ms=0.0,
            success=False,
            error_message=f"Replay failed after {self.max_retries} retries: {last_error}"
        )

    def replay_request_sync(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        mock_response: Optional[Tuple[int, Dict[str, Any]]] = None
    ) -> ReplayResponse:
        """Synchronous wrapper for executing replay request."""
        return asyncio.run(
            self.replay_request_async(
                method=method,
                path=path,
                params=params,
                json_body=json_body,
                mock_response=mock_response
            )
        )
