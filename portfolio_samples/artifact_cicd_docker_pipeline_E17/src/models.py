"""Data contracts, models, and enums for Containerization & CI/CD Deployment Automation.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


class ContainerStage(str, Enum):
    BUILDER = "BUILDER"
    RUNTIME = "RUNTIME"
    TEST = "TEST"


class HealthCheckStatus(str, Enum):
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    STARTING = "STARTING"
    UNKNOWN = "UNKNOWN"


class DeploymentStrategy(str, Enum):
    BLUE_GREEN = "BLUE_GREEN"
    ROLLING = "ROLLING"
    RECREATE = "RECREATE"


class DeploymentStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass
class ServiceResourceLimits:
    cpus: float
    memory_limit_mb: int
    memory_reservation_mb: int


@dataclass
class ServiceSpec:
    service_name: str
    image_tag: str
    container_port: int
    host_port: int
    restart_policy: str
    resource_limits: ServiceResourceLimits
    healthcheck_command: str
    healthcheck_interval_seconds: int = 10
    healthcheck_retries: int = 3


@dataclass
class DockerfileLintIssue:
    line_number: int
    severity: str  # CRITICAL, WARNING, INFO
    rule_id: str
    message: str


@dataclass
class DockerfileLintReport:
    is_multi_stage: bool
    runs_as_non_root: bool
    uses_minimal_base: bool
    secrets_leaked: bool
    issues: List[DockerfileLintIssue] = field(default_factory=list)
    score: int = 100


@dataclass
class ComposeValidationReport:
    total_services: int
    all_healthchecks_defined: bool
    all_resource_limits_defined: bool
    all_log_rotations_configured: bool
    port_conflicts: List[str] = field(default_factory=list)
    is_valid: bool = True


@dataclass
class DeploymentRecord:
    deployment_id: str
    strategy: DeploymentStrategy
    image_tag: str
    active_container_id: str
    previous_container_id: Optional[str]
    status: DeploymentStatus
    health_check_status: HealthCheckStatus
    rollback_triggered: bool
    elapsed_seconds: float
    deployed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeploymentAuditLog:
    run_id: str
    deployment_id: str
    strategy: str
    image_tag: str
    status: str
    rollback_triggered: bool
    elapsed_seconds: float
    health_check_status: str
    deployed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class HealthProbeEvent:
    probe_id: str
    container_id: str
    status: HealthCheckStatus
    latency_ms: float
    probe_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
