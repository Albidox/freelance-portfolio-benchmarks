"""Standalone deterministic test harness for E17 CI/CD Docker Pipeline with 26 assertions.
Runs natively on Windows without Linux shell dependencies.
Strict zero em dash policy enforced.
"""
import os
import sys
import time
import tracemalloc

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.models import (
    ContainerStage,
    HealthCheckStatus,
    DeploymentStrategy,
    DeploymentStatus,
    ServiceResourceLimits,
    ServiceSpec,
    DockerfileLintReport,
    ComposeValidationReport,
    DeploymentRecord
)
from src.config import DeploymentPipelineConfig
from src.docker_linter import DockerLinter
from src.compose_validator import ComposeValidator
from src.workflow_builder import WorkflowBuilder
from src.deploy_vps import VPSDeploymentEngine
from src.storage import DeploymentStorage


def test_models_and_configuration():
    print("Testing data contracts and system configuration...")
    config = DeploymentPipelineConfig()

    # Assertion 1: PostgreSQL target port matches local native instance
    assert config.pg_port == 5433
    # Assertion 2: Target schema is isolated
    assert config.target_schema == "e17_cicd_pipeline"
    # Assertion 3: Default strategy is BLUE_GREEN
    assert config.default_strategy == "BLUE_GREEN"
    # Assertion 4: Health check timeout is 10.0 seconds
    assert config.health_check_timeout_seconds == 10.0


def test_dockerfile_linter_and_security():
    print("Testing Dockerfile AST linter and security checks...")
    linter = DockerLinter()

    valid_dockerfile = """FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-distroless AS runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY src/ ./src/
USER appuser
CMD ["python", "src/main.py"]
"""
    report_valid = linter.lint_dockerfile_content(valid_dockerfile)
    # Assertion 5: Multi-stage build recognized
    assert report_valid.is_multi_stage is True
    # Assertion 6: Non-root user directive recognized
    assert report_valid.runs_as_non_root is True
    # Assertion 7: Minimal base image recognized
    assert report_valid.uses_minimal_base is True
    # Assertion 8: No secrets leaked in valid Dockerfile
    assert report_valid.secrets_leaked is False
    # Assertion 9: Perfect score on clean Dockerfile
    assert report_valid.score == 100

    insecure_dockerfile = """FROM python:3.11
WORKDIR /app
COPY .env /app/.env
CMD ["python", "main.py"]
"""
    report_insecure = linter.lint_dockerfile_content(insecure_dockerfile)
    # Assertion 10: Secret leak detected on .env reference
    assert report_insecure.secrets_leaked is True
    # Assertion 11: Insecure Dockerfile flagged for root execution
    assert report_insecure.runs_as_non_root is False


def test_compose_validator_and_resources():
    print("Testing docker-compose manifest validation...")
    validator = ComposeValidator()

    valid_compose = {
        "services": {
            "web": {
                "image": "app:latest",
                "ports": ["8080:8080"],
                "healthcheck": {
                    "test": ["CMD", "curl", "-f", "http://localhost:8080/healthz"],
                    "interval": "10s"
                },
                "deploy": {
                    "resources": {
                        "limits": {"cpus": "1.0", "memory": "512M"}
                    }
                },
                "logging": {
                    "options": {"max-size": "10m", "max-file": "3"}
                }
            }
        }
    }
    report_valid = validator.validate_compose_dict(valid_compose)
    # Assertion 12: Compose valid state is True
    assert report_valid.is_valid is True
    # Assertion 13: Service count equals 1
    assert report_valid.total_services == 1
    # Assertion 14: All healthchecks defined
    assert report_valid.all_healthchecks_defined is True
    # Assertion 15: All resource limits defined
    assert report_valid.all_resource_limits_defined is True

    # Test port collision detection
    colliding_compose = {
        "services": {
            "web_a": {"ports": ["8080:8080"]},
            "web_b": {"ports": ["8080:8081"]}
        }
    }
    report_collision = validator.validate_compose_dict(colliding_compose)
    # Assertion 16: Port conflict detected
    assert len(report_collision.port_conflicts) > 0


def test_workflow_builder_and_matrix():
    print("Testing GitHub Actions CI/CD workflow generator...")
    builder = WorkflowBuilder()
    yaml_text = builder.generate_deploy_workflow_yaml(
        image_name="enterprise-app",
        enable_buildx_cache=True,
        enable_security_scan=True
    )
    val = builder.validate_workflow_text(yaml_text)
    # Assertion 17: Buildx action step present
    assert val["has_buildx"] is True
    # Assertion 18: Buildx GitHub cache configured
    assert val["has_cache"] is True
    # Assertion 19: Trivy security scan configured
    assert val["has_security_scan"] is True
    # Assertion 20: Test runner execution step present
    assert val["runs_test_suite"] is True


def test_vps_deployment_engine_and_rollback():
    print("Testing VPS zero-downtime deployment and auto-rollback...")
    config = DeploymentPipelineConfig()
    engine = VPSDeploymentEngine(config)

    # Test successful deployment
    rec_ok = engine.deploy_release(
        deployment_id="dep_001_success",
        image_tag="ghcr.io/app:v1.1.0"
    )
    # Assertion 21: Successful deployment status is SUCCESSFUL
    assert rec_ok.status == DeploymentStatus.SUCCESSFUL
    # Assertion 22: Rollback was not triggered
    assert rec_ok.rollback_triggered is False
    # Assertion 23: Active container ID updated to candidate
    assert "dep_001_" in rec_ok.active_container_id

    # Test simulated failure and automatic rollback
    engine.simulated_health_failure = True
    rec_fail = engine.deploy_release(
        deployment_id="dep_002_fail",
        image_tag="ghcr.io/app:v2.0.0"
    )
    # Assertion 24: Failed deployment status is ROLLED_BACK
    assert rec_fail.status == DeploymentStatus.ROLLED_BACK
    # Assertion 25: Rollback was triggered
    assert rec_fail.rollback_triggered is True


def test_dual_tier_storage_audit():
    print("Testing SQLite WAL deployment audit persistence...")
    test_db = os.path.join(CURRENT_DIR, "test_deploy_audit.db")
    if os.path.exists(test_db):
        os.remove(test_db)

    config = DeploymentPipelineConfig(sqlite_audit_path=test_db)
    storage = DeploymentStorage(config)

    rec = DeploymentRecord(
        deployment_id="dep_audit_test",
        strategy=DeploymentStrategy.BLUE_GREEN,
        image_tag="ghcr.io/app:v1.0.0",
        active_container_id="c_live",
        previous_container_id="c_prev",
        status=DeploymentStatus.SUCCESSFUL,
        health_check_status=HealthCheckStatus.HEALTHY,
        rollback_triggered=False,
        elapsed_seconds=2.45
    )
    storage.record_deployment(rec)
    loaded = storage.get_deployment("dep_audit_test")

    try:
        # Assertion 26: Stored deployment retrieved successfully with matching status
        assert loaded is not None
        assert loaded["status"] == "SUCCESSFUL"
    finally:
        if os.path.exists(test_db):
            os.remove(test_db)
        # Also clean up WAL and SHM files if present
        for ext in ["-wal", "-shm"]:
            if os.path.exists(test_db + ext):
                os.remove(test_db + ext)


def main():
    print("=" * 70)
    print("RUNNING DETERMINISTIC TEST HARNESS: E17 CONTAINERIZATION & CI/CD PIPELINE")
    print("Platform: Windows 10 | Target DB: Native PostgreSQL 18 (:5433)")
    print("=" * 70)

    tracemalloc.start()
    start_time = time.perf_counter()

    test_models_and_configuration()
    test_dockerfile_linter_and_security()
    test_compose_validator_and_resources()
    test_workflow_builder_and_matrix()
    test_vps_deployment_engine_and_rollback()
    test_dual_tier_storage_audit()

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.perf_counter() - start_time

    print("-" * 70)
    print("ALL 26 ASSERTIONS PASSED WITH 100% SUCCESS RATE")
    print(f"Elapsed Time: {elapsed:.4f} seconds")
    print(f"Memory Footprint: Peak = {peak_mem / 1024 / 1024:.2f} MB (Cap: 250 MB)")
    print("=" * 70)


if __name__ == "__main__":
    main()
