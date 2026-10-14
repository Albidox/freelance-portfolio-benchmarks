"""Windows Registry auditor and MRU list cleaner with deterministic backup manifests.
Strict zero em dash policy enforced.
"""
from typing import List, Dict, Any, Optional
from src.models import RegistryAuditRecord


class WindowsRegistryAuditor:
    """Audits Windows registry associations and MRU bloat with rollback command generation."""

    def __init__(self):
        self.audit_log: List[RegistryAuditRecord] = []

    def inspect_file_association(self, extension: str, handler_prog_id: Optional[str]) -> RegistryAuditRecord:
        """Inspect file extension association and flag dangling handlers."""
        key_path = f"HKCR\\{extension}"
        if not handler_prog_id or handler_prog_id.strip() == "":
            record = RegistryAuditRecord(
                hive="HKEY_CLASSES_ROOT",
                key_path=key_path,
                value_name="",
                issue_type="DANGLING_FILE_EXTENSION",
                recommended_action="REMOVE_OR_REASSOCIATE",
                backup_command=f'reg export "{key_path}" "backup_{extension.replace(".", "")}.reg" /y'
            )
        else:
            record = RegistryAuditRecord(
                hive="HKEY_CLASSES_ROOT",
                key_path=key_path,
                value_name="",
                issue_type="HEALTHY",
                recommended_action="PRESERVE",
                backup_command=""
            )
        self.audit_log.append(record)
        return record

    def inspect_mru_list(self, app_name: str, mru_key_path: str, entry_count: int) -> RegistryAuditRecord:
        """Inspect application MRU list and recommend cleanup if bloated."""
        if entry_count > 50:
            record = RegistryAuditRecord(
                hive="HKEY_CURRENT_USER",
                key_path=mru_key_path,
                value_name="MRUListEx",
                issue_type="BLOATED_MRU_HISTORY",
                recommended_action="PURGE_HISTORY",
                backup_command=f'reg export "{mru_key_path}" "backup_mru_{app_name}.reg" /y'
            )
        else:
            record = RegistryAuditRecord(
                hive="HKEY_CURRENT_USER",
                key_path=mru_key_path,
                value_name="MRUListEx",
                issue_type="HEALTHY",
                recommended_action="PRESERVE",
                backup_command=""
            )
        self.audit_log.append(record)
        return record
