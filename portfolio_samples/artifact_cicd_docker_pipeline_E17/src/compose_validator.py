"""Validator for docker-compose manifests verifying healthchecks, limits, and logging.
Strict zero em dash policy enforced.
"""
import os
from typing import Dict, Any, List
from src.models import ComposeValidationReport


class ComposeValidator:
    """Validates docker-compose service definitions for production readiness."""

    def __init__(self):
        pass

    def validate_compose_file(self, filepath: str) -> ComposeValidationReport:
        """Parses and validates a docker-compose.yml file from disk."""
        if not os.path.exists(filepath):
            return ComposeValidationReport(
                total_services=0,
                all_healthchecks_defined=False,
                all_resource_limits_defined=False,
                all_log_rotations_configured=False,
                port_conflicts=[f"File not found: {filepath}"],
                is_valid=False
            )
        try:
            import yaml
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return self.validate_compose_dict(data or {})
        except Exception as e:
            return ComposeValidationReport(
                total_services=0,
                all_healthchecks_defined=False,
                all_resource_limits_defined=False,
                all_log_rotations_configured=False,
                port_conflicts=[f"YAML parsing error: {str(e)}"],
                is_valid=False
            )

    def validate_compose_dict(self, compose_data: Dict[str, Any]) -> ComposeValidationReport:
        """Validates in-memory dictionary of compose configuration."""
        services = compose_data.get("services", {})
        total_services = len(services)

        all_healthchecks = True
        all_resources = True
        all_logs = True
        port_conflicts = []
        seen_host_ports = {}

        for s_name, s_def in services.items():
            if not isinstance(s_def, dict):
                continue

            # Check healthcheck
            if "healthcheck" not in s_def:
                all_healthchecks = False

            # Check resource limits (deploy.resources.limits)
            deploy = s_def.get("deploy", {})
            limits = deploy.get("resources", {}).get("limits", {}) if isinstance(deploy, dict) else {}
            if not isinstance(limits, dict) or "cpus" not in limits or "memory" not in limits:
                all_resources = False

            # Check logging max-size and max-file
            logging_cfg = s_def.get("logging", {})
            opts = logging_cfg.get("options", {}) if isinstance(logging_cfg, dict) else {}
            if not isinstance(opts, dict) or "max-size" not in opts or "max-file" not in opts:
                all_logs = False

            # Check host port binding collisions
            ports = s_def.get("ports", [])
            for p in ports:
                p_str = str(p)
                if ":" in p_str:
                    host_part = p_str.split(":")[0]
                    if host_part in seen_host_ports:
                        port_conflicts.append(f"Port {host_part} conflict between {seen_host_ports[host_part]} and {s_name}")
                    seen_host_ports[host_part] = s_name

        is_valid = total_services > 0 and all_healthchecks and all_resources and all_logs and len(port_conflicts) == 0

        return ComposeValidationReport(
            total_services=total_services,
            all_healthchecks_defined=all_healthchecks,
            all_resource_limits_defined=all_resources,
            all_log_rotations_configured=all_logs,
            port_conflicts=port_conflicts,
            is_valid=is_valid
        )
