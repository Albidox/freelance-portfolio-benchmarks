"""System health metric sampler and composite health score calculator.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any
from src.models import SystemHealthSnapshot


class WindowsHealthMonitor:
    """Monitors system resource pressure and computes composite system health score."""

    def __init__(self):
        pass

    def compute_health_score(self, cpu_pct: float, ram_pct: float, disk_free_pct: float) -> int:
        """Calculate composite health score from 0 (critical) to 100 (optimal)."""
        score = 100.0

        # CPU penalty: if CPU > 80%, penalize up to 25 points
        if cpu_pct > 80.0:
            score -= min(25.0, (cpu_pct - 80.0) * 1.25)

        # RAM penalty: if RAM > 85%, penalize up to 35 points
        if ram_pct > 85.0:
            score -= min(35.0, (ram_pct - 85.0) * 2.33)

        # Disk penalty: if Free Disk < 15%, penalize up to 40 points
        if disk_free_pct < 15.0:
            score -= min(40.0, (15.0 - disk_free_pct) * 2.67)

        return max(0, min(100, int(round(score))))

    def generate_snapshot(
        self,
        cpu_usage_pct: float,
        ram_total_gb: float,
        ram_used_gb: float,
        disk_total_gb: float,
        disk_free_gb: float
    ) -> SystemHealthSnapshot:
        """Assemble complete system health snapshot with computed scores."""
        ram_pct = round((ram_used_gb / ram_total_gb) * 100.0, 1) if ram_total_gb > 0 else 0.0
        disk_free_pct = round((disk_free_gb / disk_total_gb) * 100.0, 1) if disk_total_gb > 0 else 0.0
        health_score = self.compute_health_score(cpu_usage_pct, ram_pct, disk_free_pct)

        return SystemHealthSnapshot(
            cpu_usage_pct=round(cpu_usage_pct, 1),
            ram_total_gb=round(ram_total_gb, 1),
            ram_used_gb=round(ram_used_gb, 1),
            ram_percent=ram_pct,
            disk_total_gb=round(disk_total_gb, 1),
            disk_free_gb=round(disk_free_gb, 1),
            disk_free_pct=disk_free_pct,
            health_score=health_score
        )
