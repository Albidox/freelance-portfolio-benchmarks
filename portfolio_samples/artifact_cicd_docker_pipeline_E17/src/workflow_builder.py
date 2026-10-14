"""Generator and validator for GitHub Actions CI/CD workflow manifests.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any


class WorkflowBuilder:
    """Constructs and validates GitHub Actions CI/CD deployment pipelines."""

    def __init__(self):
        pass

    def generate_deploy_workflow_yaml(
        self,
        image_name: str,
        registry: str = "ghcr.io",
        enable_buildx_cache: bool = True,
        enable_security_scan: bool = True
    ) -> str:
        """Generates multi-arch GitHub Actions deploy workflow with buildx cache."""
        buildx_cache_block = ""
        if enable_buildx_cache:
            buildx_cache_block = """          cache-from: type=gha\n          cache-to: type=gha,mode=max"""

        security_scan_block = ""
        if enable_security_scan:
            security_scan_block = """      - name: Scan Image with Trivy\n        uses: aquasecurity/trivy-action@master\n        with:\n          image-ref: ${{ env.IMAGE_TAG }}\n          format: 'table'\n          exit-code: '1'\n          ignore-unfixed: true\n          severity: 'CRITICAL,HIGH'"""

        yaml_content = f"""name: Production CI/CD Deployment

on:
  push:
    branches: [ main ]
    tags: [ 'v*.*.*' ]

env:
  REGISTRY: {registry}
  IMAGE_NAME: {image_name}
  IMAGE_TAG: {registry}/{image_name}:${{{{ github.sha }}}}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Run Test Suite
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          python run_tests.py

  build_and_deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Build and Push Docker Image
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{{{ env.IMAGE_TAG }}}}
{buildx_cache_block}
{security_scan_block}
      - name: Trigger Idempotent VPS Deployment
        run: |
          python deploy_vps.py --image ${{{{ env.IMAGE_TAG }}}} --strategy BLUE_GREEN
"""
        return yaml_content

    def validate_workflow_text(self, workflow_text: str) -> Dict[str, Any]:
        """Validates that CI/CD workflow meets production criteria."""
        has_buildx = "docker/setup-buildx-action" in workflow_text
        has_cache = "type=gha" in workflow_text
        has_security = "trivy-action" in workflow_text or "trivy" in workflow_text
        has_tests = "python run_tests.py" in workflow_text or "pytest" in workflow_text
        is_valid = has_buildx and has_cache and has_security and has_tests

        return {
            "has_buildx": has_buildx,
            "has_cache": has_cache,
            "has_security_scan": has_security,
            "runs_test_suite": has_tests,
            "is_valid": is_valid
        }
