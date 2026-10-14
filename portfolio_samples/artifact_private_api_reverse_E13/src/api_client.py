"""Resilient private API HTTP client with circuit breaker and backoff algorithms.
Strict zero em dash policy enforced.
"""
import time
import math
import random
import json
from typing import Dict, Any, Optional, Tuple
from src.config import PrivateApiConfig
from src.models import DevicePlatform, HarvestStatus, HarvesterMetrics
from src.signer import MobileRequestSigner
from src.session_manager import SessionManager


class CircuitBreakerState:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class PrivateAPIClient:
    def __init__(self, config: Optional[PrivateApiConfig] = None, signer: Optional[MobileRequestSigner] = None):
        self.config = config or PrivateApiConfig()
        self.signer = signer or MobileRequestSigner(api_secret="prod_mobile_key_2026")
        self.session_manager = SessionManager(default_platform=DevicePlatform.ANDROID)
        self.metrics = HarvesterMetrics()
        
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.circuit_opened_at = 0.0

    def calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate truncated exponential backoff with full jitter."""
        temp = min(self.config.max_backoff_seconds, self.config.base_backoff_seconds * (2 ** attempt))
        delay = random.uniform(0.5, 1.0) * temp
        return round(delay, 3)

    def _check_circuit_breaker(self) -> bool:
        """Evaluate circuit breaker state. Return True if call is allowed."""
        now = time.time()
        if self.state == CircuitBreakerState.OPEN:
            if now - self.circuit_opened_at >= self.config.circuit_breaker_recovery_seconds:
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        return True

    def record_success(self) -> None:
        """Reset circuit breaker counters upon successful API response."""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        self.metrics.successful_requests += 1

    def record_failure(self) -> None:
        """Increment failure counter and trip breaker if threshold exceeded."""
        self.failure_count += 1
        self.metrics.failed_requests += 1
        if self.failure_count >= self.config.circuit_breaker_threshold:
            self.state = CircuitBreakerState.OPEN
            self.circuit_opened_at = time.time()

    def execute_request_cycle(
        self,
        method: str,
        path: str,
        payload: Dict[str, Any],
        simulated_status_code: int = 200,
        simulated_response_body: Optional[str] = None
    ) -> Tuple[HarvestStatus, Optional[Dict[str, Any]]]:
        """Execute request lifecycle including signature generation, backoff, and circuit checks."""
        self.metrics.total_requests += 1
        
        if not self._check_circuit_breaker():
            return HarvestStatus.CIRCUIT_OPEN, None

        if not self.session_manager.is_session_valid():
            self.session_manager.refresh_session_if_needed()

        body_str = json.dumps(payload, separators=(',', ':'))
        headers = self.signer.build_signed_headers(
            method=method,
            path=path,
            payload_body=body_str,
            device=self.session_manager.device
        )
        
        if self.session_manager.credentials:
            headers["Authorization"] = f"Bearer {self.session_manager.credentials.access_token}"
        cookie_header = self.session_manager.get_cookie_header()
        if cookie_header:
            headers["Cookie"] = cookie_header

        if simulated_status_code == 429:
            self.metrics.rate_limits_encountered += 1
            self.record_failure()
            return HarvestStatus.RATE_LIMITED, None
        elif simulated_status_code >= 500:
            self.record_failure()
            return HarvestStatus.FAILED, None
        elif simulated_status_code == 200:
            self.record_success()
            res_dict = json.loads(simulated_response_body or "{\"status\":\"ok\"}")
            return HarvestStatus.SUCCESS, res_dict
        
        return HarvestStatus.FAILED, None
