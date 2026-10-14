"""Schema-tolerant entity extraction and corrupted payload quarantine.
Strict zero em dash policy enforced.
"""
import json
from typing import Dict, Any, Optional, List, Tuple
from src.models import ExtractedEntityRecord


class DataExtractor:
    def __init__(self, primary_id_candidates: Optional[List[str]] = None):
        self.primary_id_candidates = primary_id_candidates or [
            "id", "user_id", "entity_id", "uuid", "account_no", "item_code"
        ]
        self.quarantine_bin: List[Dict[str, Any]] = []

    def extract_record(
        self,
        endpoint_path: str,
        raw_payload: Any,
        entity_type: str = "GENERIC_ENTITY"
    ) -> Tuple[bool, Optional[ExtractedEntityRecord], bool]:
        """Extract standardized entity from raw payload.
        
        Returns:
            Tuple of (success, record, is_schema_drifted)
        """
        if not isinstance(raw_payload, dict):
            self.quarantine_bin.append({"endpoint": endpoint_path, "raw": str(raw_payload), "reason": "non_dict_payload"})
            return False, None, False

        is_drifted = False
        target_dict = raw_payload
        for wrapper_key in ["data", "result", "payload", "response"]:
            if wrapper_key in target_dict and isinstance(target_dict[wrapper_key], dict):
                target_dict = target_dict[wrapper_key]
                is_drifted = True
                break

        found_id: Optional[str] = None
        for candidate in self.primary_id_candidates:
            if candidate in target_dict and target_dict[candidate] is not None:
                found_id = str(target_dict[candidate])
                break

        if not found_id:
            self.quarantine_bin.append({
                "endpoint": endpoint_path,
                "payload": target_dict,
                "reason": "missing_primary_id"
            })
            return False, None, is_drifted

        record = ExtractedEntityRecord(
            entity_id=found_id,
            entity_type=entity_type,
            source_endpoint=endpoint_path,
            payload=target_dict
        )
        return True, record, is_drifted
