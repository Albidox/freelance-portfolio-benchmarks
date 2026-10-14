"""DISM and SFC health scan executor with corruption detection and log parsing.
Strict zero em dash policy enforced.
"""
import re
import time
from typing import Dict, Any, Optional, List
from src.models import HealthScanResult


class WindowsHealthScanner:
    """Executes or parses Windows SFC and DISM system integrity scans."""

    def __init__(self):
        pass

    def parse_sfc_output(self, stdout_text: str, duration: float = 0.0) -> HealthScanResult:
        """Parse sfc /scannow console output for corruption and repair indicators."""
        text = stdout_text.lower()
        corrupted = False
        repaired = True

        if "found corrupt files" in text or "corrupted" in text:
            corrupted = True
            if "unable to fix" in text or "could not fix" in text or "failed" in text:
                repaired = False
            else:
                repaired = True
        elif "did not find any integrity violations" in text:
            corrupted = False
            repaired = True

        summary = "Integrity check clean"
        if corrupted:
            summary = "Corrupt files found and successfully repaired" if repaired else "Corrupt files found, repair incomplete"

        return HealthScanResult(
            scan_type="SFC",
            corrupted_files_found=corrupted,
            repair_successful=repaired,
            log_summary=summary,
            duration_seconds=round(duration, 3)
        )

    def parse_dism_output(self, stdout_text: str, duration: float = 0.0) -> HealthScanResult:
        """Parse DISM /Online /Cleanup-Image /ScanHealth console output."""
        text = stdout_text.lower()
        corrupted = False
        repaired = True

        if "no component store corruption detected" in text:
            corrupted = False
            repaired = True
            summary = "No component store corruption detected"
        elif "component store is repairable" in text or "corruption detected" in text:
            corrupted = True
            repaired = True
            summary = "Component store corruption detected and repairable"
        else:
            summary = "DISM scan completed"

        return HealthScanResult(
            scan_type="DISM",
            corrupted_files_found=corrupted,
            repair_successful=repaired,
            log_summary=summary,
            duration_seconds=round(duration, 3)
        )

    def simulate_integrity_scan(self, simulate_corruption: bool = False) -> List[HealthScanResult]:
        """Perform simulated deterministic system integrity scan."""
        results = []
        if not simulate_corruption:
            sfc_log = "Windows Resource Protection did not find any integrity violations."
            dism_log = "The component store is repairable. The operation completed successfully. No component store corruption detected."
            results.append(self.parse_sfc_output(sfc_log, 0.45))
            results.append(self.parse_dism_output(dism_log, 0.60))
        else:
            sfc_log = "Windows Resource Protection found corrupt files and successfully repaired them."
            dism_log = "The component store corruption detected. The restore operation completed successfully."
            results.append(self.parse_sfc_output(sfc_log, 1.20))
            results.append(self.parse_dism_output(dism_log, 1.50))
        return results
