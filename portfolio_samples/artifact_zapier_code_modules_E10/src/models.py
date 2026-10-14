"""Data contracts, models, and enums for Zapier & Make.com Code Modules.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import json


class ExecutionEnvironment(str, Enum):
    ZAPIER = "ZAPIER"
    MAKE = "MAKE"
    LOCAL_CLI = "LOCAL_CLI"


class TransformationType(str, Enum):
    FLATTEN = "FLATTEN"
    NORMALIZE = "NORMALIZE"
    FILTER = "FILTER"
    AGGREGATE = "AGGREGATE"


class RateLimitStrategy(str, Enum):
    LEAKY_BUCKET = "LEAKY_BUCKET"
    TOKEN_BUCKET = "TOKEN_BUCKET"
    EXPONENTIAL_BACKOFF = "EXPONENTIAL_BACKOFF"


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


@dataclass
class StepInputBundle:
    input_data: Dict[str, Any]
    environment: ExecutionEnvironment = ExecutionEnvironment.LOCAL_CLI
    max_duration_ms: int = 9500
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate(self) -> bool:
        """Validate input bundle attributes."""
        if not isinstance(self.input_data, dict):
            return False
        if self.max_duration_ms <= 0:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_data": self.input_data,
            "environment": self.environment.value,
            "max_duration_ms": self.max_duration_ms,
            "created_at": self.created_at,
        }


@dataclass
class StepOutputBundle:
    output_data: Dict[str, Any]
    execution_duration_ms: float
    status: ExecutionStatus
    error_message: Optional[str] = None
    telemetry: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output_data": self.output_data,
            "execution_duration_ms": self.execution_duration_ms,
            "status": self.status.value,
            "error_message": self.error_message,
            "telemetry": self.telemetry,
        }


@dataclass
class JWTConfig:
    algorithm: str = "HS256"
    issuer: str = "zapier_breakout_e10"
    subject: str = "client_auth"
    audience: str = "api_gateway"
    ttl_seconds: int = 3600
    secret_key: str = "dev_secret_key_change_in_production"


@dataclass
class RateLimitConfig:
    max_requests: int = 60
    time_window_seconds: int = 60
    retry_after_seconds: int = 5
    max_backoff_seconds: int = 8


@dataclass
class AuditLogRecord:
    log_id: str
    module_name: str
    environment: str
    duration_ms: float
    status: str
    details: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TransformerInput:
    input_payload: Dict[str, Any]
    delimiter: str = "_"
    normalize_case: bool = True
    target_schema: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TransformationResult:
    transformed_payload: Dict[str, Any]
    record_count: int
    execution_time_ms: float
    success: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditReceipt:
    receipt_id: str
    module: str
    status: str
    duration_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
