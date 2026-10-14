"""Windows background service tuner disabling resource-heavy telemetry and non-essential startup bloat.
Strict zero em dash policy enforced.
"""
from typing import List, Dict, Any, Optional
from src.models import ServiceStartupType, ServiceAuditRecord, ServiceTuningRule
from src.config import WindowsOptimizerConfig
from src.service_optimizer import WindowsServiceOptimizer


class WindowsServiceTuner(WindowsServiceOptimizer):
    """Windows background service tuner for disabling bloatware and telemetry."""

    def __init__(self, config: Optional[WindowsOptimizerConfig] = None):
        super().__init__(config)

    def get_default_tuning_rules(self) -> List[ServiceTuningRule]:
        """Return standardized tuning rules for Windows 10/11 commercial environments."""
        rules = []
        for name, info in self.known_bloat_services.items():
            rules.append(ServiceTuningRule(
                service_name=name,
                target_startup=info["recommended"],
                rationale=info["reason"],
                category=info["category"],
                requires_admin=True,
                dependencies=[]
            ))
        return rules

    def evaluate_batch(
        self,
        service_snapshots: List[Dict[str, Any]]
    ) -> List[ServiceAuditRecord]:
        """Batch audit a collection of running or configured services."""
        records = []
        for item in service_snapshots:
            name = item["name"]
            startup = item.get("startup", ServiceStartupType.UNKNOWN)
            if isinstance(startup, str):
                try:
                    startup = ServiceStartupType(startup.upper())
                except ValueError:
                    startup = ServiceStartupType.UNKNOWN
            status = item.get("status", "Unknown")
            records.append(self.audit_service(name, startup, status))
        return records
