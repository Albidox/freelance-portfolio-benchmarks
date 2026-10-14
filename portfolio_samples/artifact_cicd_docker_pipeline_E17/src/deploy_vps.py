"""Idempotent VPS deployment engine with zero-downtime rolling container swap and auto-rollback.
Strict zero em dash policy enforced.
"""
import time
from typing import Dict, Any, Optional
from src.models import DeploymentRecord, DeploymentStatus, HealthCheckStatus, DeploymentStrategy
from src.config import DeploymentPipelineConfig


class VPSDeploymentEngine:
    """Zero-downtime container release manager with health check probes and automated rollback."""

    def __init__(self, config: Optional[DeploymentPipelineConfig] = None):
        self.config = config or DeploymentPipelineConfig()
        self.active_container_id = "container_v1_live"
        self.previous_container_id: Optional[str] = None
        self.simulated_health_failure = False

    def probe_container_health(self, target_container_id: str) -> HealthCheckStatus:
        """Simulates probing HTTP health endpoint (/healthz) of target container."""
        if self.simulated_health_failure:
            return HealthCheckStatus.UNHEALTHY
        return HealthCheckStatus.HEALTHY

    def deploy_release(
        self,
        deployment_id: str,
        image_tag: str,
        strategy: DeploymentStrategy = DeploymentStrategy.BLUE_GREEN
    ) -> DeploymentRecord:
        """Executes zero-downtime deployment with health check verification and automatic rollback."""
        start_time = time.perf_counter()
        candidate_container_id = f"container_{deployment_id[:8]}_candidate"

        # Step 1: Start candidate container in parallel
        self.previous_container_id = self.active_container_id

        # Step 2: Poll candidate health
        attempts = 0
        healthy = False
        while attempts < self.config.max_health_probe_retries:
            status = self.probe_container_health(candidate_container_id)
            if status == HealthCheckStatus.HEALTHY:
                healthy = True
                break
            time.sleep(0.01)  # Simulated polling tick
            attempts += 1

        elapsed = time.perf_counter() - start_time

        # Step 3: Branch on health status
        if healthy:
            # Promote candidate to live
            self.active_container_id = candidate_container_id
            return DeploymentRecord(
                deployment_id=deployment_id,
                strategy=strategy,
                image_tag=image_tag,
                active_container_id=self.active_container_id,
                previous_container_id=self.previous_container_id,
                status=DeploymentStatus.SUCCESSFUL,
                health_check_status=HealthCheckStatus.HEALTHY,
                rollback_triggered=False,
                elapsed_seconds=round(elapsed, 4)
            )
        else:
            # Trigger immediate automatic rollback
            self.active_container_id = self.previous_container_id
            return DeploymentRecord(
                deployment_id=deployment_id,
                strategy=strategy,
                image_tag=image_tag,
                active_container_id=self.active_container_id,
                previous_container_id=candidate_container_id,
                status=DeploymentStatus.ROLLED_BACK,
                health_check_status=HealthCheckStatus.UNHEALTHY,
                rollback_triggered=True,
                elapsed_seconds=round(elapsed, 4)
            )
