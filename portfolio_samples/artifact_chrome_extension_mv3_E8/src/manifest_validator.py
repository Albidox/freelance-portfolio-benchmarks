"""Manifest V3 specification generator and schema integrity validator."""
import json
from typing import Dict, Any, Tuple, List


class ManifestValidator:
    @staticmethod
    def get_manifest_v3_spec() -> Dict[str, Any]:
        """Return canonical Manifest V3 configuration dictionary."""
        return {
            "manifest_version": 3,
            "name": "Enterprise DOM Table Data Exporter",
            "version": "1.0.0",
            "description": "High-throughput tabular data scraper and RFC 4180 CSV exporter.",
            "permissions": [
                "storage",
                "activeTab",
                "scripting",
                "alarms"
            ],
            "host_permissions": [
                "https://*/*",
                "http://*/*"
            ],
            "background": {
                "service_worker": "background.js",
                "type": "module"
            },
            "action": {
                "default_popup": "popup.html",
                "default_title": "Enterprise Data Exporter"
            },
            "content_scripts": [
                {
                    "matches": ["<all_urls>"],
                    "js": ["content_script.js"],
                    "run_at": "document_idle"
                }
            ]
        }

    @staticmethod
    def validate_manifest(manifest: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate Manifest V3 compliance rules and detect illegal V2 legacy keys."""
        errors = []
        if manifest.get("manifest_version") != 3:
            errors.append("manifest_version must be exactly 3")

        # Check for prohibited Manifest V2 keys
        prohibited_v2_keys = ["browser_action", "page_action", "background.scripts"]
        for key in prohibited_v2_keys:
            if "." in key:
                parts = key.split(".")
                if parts[0] in manifest and isinstance(manifest[parts[0]], dict) and parts[1] in manifest[parts[0]]:
                    errors.append(f"Prohibited MV2 structure detected: {key}")
            elif key in manifest:
                errors.append(f"Prohibited MV2 key detected: {key}")

        bg = manifest.get("background", {})
        if not isinstance(bg, dict) or "service_worker" not in bg:
            errors.append("Manifest V3 background must define 'service_worker'")

        action = manifest.get("action", {})
        if not isinstance(action, dict) or "default_popup" not in action:
            errors.append("Manifest V3 action must define 'default_popup'")

        return len(errors) == 0, errors
