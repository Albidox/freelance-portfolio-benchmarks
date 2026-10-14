"""Data contracts, models, and enums for Private Mobile and SPA API Reverse Engineering.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import time


class DevicePlatform(str, Enum):
    ANDROID = "ANDROID"
    IOS = "IOS"
    SPA_WEB = "SPA_WEB"


class RequestAuthType(str, Enum):
    BEARER_JWT = "BEARER_JWT"
    HMAC_SIGNATURE = "HMAC_SIGNATURE"
    SESSION_COOKIE = "SESSION_COOKIE"
    CUSTOM_HEADER = "CUSTOM_HEADER"


class HarvestStatus(str, Enum):
    SUCCESS = "SUCCESS"
    RETRYING = "RETRYING"
    RATE_LIMITED = "RATE_LIMITED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    FAILED = "FAILED"


@dataclass
class DeviceFingerprint:
    platform: DevicePlatform
    os_version: str
    app_version: str
    device_id: str
    user_agent: str
    ja3_fingerprint: str
    ja4_fingerprint: str

    def to_headers(self) -> Dict[str, str]:
        """Convert device parameters into standardized mobile headers."""
        return {
            "X-Device-Id": self.device_id,
            "X-Device-Platform": self.platform.value,
            "X-App-Version": self.app_version,
            "X-OS-Version": self.os_version,
            "User-Agent": self.user_agent,
        }


@dataclass
class ApiSignatureRequest:
    method: str
    endpoint_path: str
    timestamp_epoch: int
    nonce: str
    payload_body: str
    api_secret: str

    def to_canonical_string(self) -> str:
        """Construct deterministic canonical payload string for cryptographic signing."""
        clean_method = self.method.strip().upper()
        clean_path = self.endpoint_path.strip().lower()
        return f"{clean_method}|{clean_path}|{self.timestamp_epoch}|{self.nonce}|{self.payload_body}"


@dataclass
class SessionCredentials:
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at_epoch: float = 0.0
    cookies: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self, skew_seconds: float = 30.0) -> bool:
        """Check if token is expired with configurable safety skew window."""
        now_epoch = datetime.now(timezone.utc).timestamp()
        return (now_epoch + skew_seconds) >= self.expires_at_epoch


@dataclass
class ExtractedEntityRecord:
    entity_id: str
    entity_type: str
    source_endpoint: str
    payload: Dict[str, Any]
    extracted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HarvesterMetrics:
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limits_encountered: int = 0
    schema_drifts_handled: int = 0
    quarantined_records: int = 0


@dataclass
class TrafficIntercept:
    flow_id: str
    timestamp: float
    client_ip: str
    server_host: str
    method: str
    path: str
    http_version: str
    headers: Dict[str, str] = field(default_factory=dict)
    payload: Optional[str] = None
    content_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BearerToken:
    token_value: str
    token_type: str = "Bearer"
    extracted_from_header: str = "Authorization"
    issued_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    claims: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self, skew_seconds: float = 30.0) -> bool:
        if self.expires_at is None:
            return False
        return (time.time() + skew_seconds) >= self.expires_at

    def to_header_value(self) -> str:
        return f"{self.token_type} {self.token_value}"


@dataclass
class ExtractedEndpoint:
    path: str
    method: str
    auth_type: RequestAuthType
    required_headers: List[str] = field(default_factory=list)
    query_params: List[str] = field(default_factory=list)
    body_schema: Optional[Dict[str, Any]] = None
    sample_response_code: int = 200

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReplayResponse:
    endpoint: str
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body_json: Optional[Dict[str, Any]] = None
    raw_text: str = ""
    latency_ms: float = 0.0
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
