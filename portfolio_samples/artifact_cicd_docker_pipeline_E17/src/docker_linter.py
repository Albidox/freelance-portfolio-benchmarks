"""AST and rule-based linter for Dockerfiles validating security, non-root, and layers.
Strict zero em dash policy enforced.
"""
import os
import re
from typing import List, Dict, Any
from src.models import DockerfileLintReport, DockerfileLintIssue


class DockerLinter:
    """AST and pattern-based Dockerfile security and multi-stage validator."""

    FORBIDDEN_SECRET_PATTERNS = [
        re.compile(r"\.env(\s|$)", re.IGNORECASE),
        re.compile(r"id_rsa", re.IGNORECASE),
        re.compile(r"aws_access_key_id", re.IGNORECASE),
        re.compile(r"BEGIN\s+RSA\s+PRIVATE\s+KEY", re.IGNORECASE)
    ]
    MINIMAL_BASE_IMAGES = ["distroless", "alpine", "slim", "scratch"]

    def __init__(self):
        pass

    def lint_file(self, filepath: str) -> DockerfileLintReport:
        """Lints a Dockerfile from on-disk path."""
        if not os.path.exists(filepath):
            return DockerfileLintReport(
                is_multi_stage=False,
                runs_as_non_root=False,
                uses_minimal_base=False,
                secrets_leaked=False,
                issues=[DockerfileLintIssue(line_number=0, severity="CRITICAL", rule_id="ERR_FILE_NOT_FOUND", message=f"File not found: {filepath}")],
                score=0
            )
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return self.lint_dockerfile_content(content)

    def lint_dockerfile_content(self, content: str) -> DockerfileLintReport:
        """Analyzes Dockerfile text content and produces a structured report."""
        lines = content.splitlines()
        issues: List[DockerfileLintIssue] = []

        from_stages = []
        user_directives = []
        base_images = []
        secrets_leaked = False

        for idx, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            # Detect FROM statements
            if line.upper().startswith("FROM "):
                parts = line.split()
                if len(parts) >= 2:
                    base_img = parts[1].lower()
                    base_images.append(base_img)
                    if " AS " in line.upper():
                        stage_name = parts[-1]
                        from_stages.append(stage_name)
                    else:
                        from_stages.append("unnamed")

            # Detect USER directives
            if line.upper().startswith("USER "):
                user_name = line.split()[1]
                user_directives.append(user_name)

            # Detect secret leaks in COPY / ADD / ENV
            for pattern in self.FORBIDDEN_SECRET_PATTERNS:
                if pattern.search(line):
                    secrets_leaked = True
                    issues.append(
                        DockerfileLintIssue(
                            line_number=idx,
                            severity="CRITICAL",
                            rule_id="SEC_001_SECRET_LEAK",
                            message=f"Potential secret file or token referenced: {line}"
                        )
                    )

        # Verification rules
        is_multi_stage = len(from_stages) > 1
        runs_as_non_root = any(u not in ("root", "0") for u in user_directives)

        # Check if final runtime stage uses minimal base
        final_base = base_images[-1] if base_images else ""
        uses_minimal_base = any(m in final_base for m in self.MINIMAL_BASE_IMAGES)

        if not is_multi_stage:
            issues.append(
                DockerfileLintIssue(
                    line_number=1,
                    severity="WARNING",
                    rule_id="PERF_001_SINGLE_STAGE",
                    message="Dockerfile does not use multi-stage build separation."
                )
            )

        if not runs_as_non_root:
            issues.append(
                DockerfileLintIssue(
                    line_number=len(lines) if lines else 1,
                    severity="CRITICAL",
                    rule_id="SEC_002_ROOT_EXECUTION",
                    message="Dockerfile does not set a non-root USER in runtime image."
                )
            )

        critical_count = len([i for i in issues if i.severity == "CRITICAL"])
        warning_count = len([i for i in issues if i.severity == "WARNING"])
        score = max(0, 100 - (critical_count * 35) - (warning_count * 15))

        return DockerfileLintReport(
            is_multi_stage=is_multi_stage,
            runs_as_non_root=runs_as_non_root,
            uses_minimal_base=uses_minimal_base,
            secrets_leaked=secrets_leaked,
            issues=issues,
            score=score
        )
