"""Type converter translating MySQL and MongoDB structures into PostgreSQL 18 schemas.
Strict zero em dash policy enforced.
"""
import re
import json
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime
from src.models import TargetDataType, ColumnMapping, QuarantineRecord


class SchemaTransformer:
    """Translates heterogeneous database records to target PostgreSQL 18 schemas."""

    def __init__(self, quarantine_invalid: bool = True):
        self.quarantine_invalid = quarantine_invalid
        self.quarantined_records: List[QuarantineRecord] = []

    def sanitize_mysql_zero_date(self, value: Any) -> Optional[str]:
        """Converts MySQL zero-dates (0000-00-00 00:00:00) and invalid dates to None."""
        if value is None:
            return None
        str_val = str(value).strip()
        if str_val in ("0000-00-00", "0000-00-00 00:00:00", "0000-00-00T00:00:00"):
            return None
        if re.match(r"^\d{4}-\d{2}-\d{2}", str_val):
            return str_val
        return None

    def transform_mysql_datatype(self, mysql_type: str) -> TargetDataType:
        """Maps MySQL column data types to PostgreSQL 18 equivalents."""
        type_upper = mysql_type.upper()
        if "TINYINT(1)" in type_upper or "BOOLEAN" in type_upper:
            return TargetDataType.BOOLEAN
        if "BIGINT" in type_upper or "SERIAL" in type_upper:
            return TargetDataType.BIGINT
        if "INT" in type_upper or "MEDIUMINT" in type_upper:
            return TargetDataType.INTEGER
        if "DECIMAL" in type_upper or "NUMERIC" in type_upper:
            return TargetDataType.NUMERIC
        if "JSON" in type_upper or ("LONGTEXT" in type_upper and "JSON" in mysql_type.lower()):
            return TargetDataType.JSONB
        if "TEXT" in type_upper:
            return TargetDataType.TEXT
        if "DATETIME" in type_upper or "TIMESTAMP" in type_upper:
            return TargetDataType.TIMESTAMP
        return TargetDataType.VARCHAR

    def transform_mongo_document(self, doc: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """Normalizes MongoDB document: maps _id to id, maps nested dicts/lists to JSONB."""
        normalized: Dict[str, Any] = {}
        try:
            raw_id = doc.get("_id")
            if isinstance(raw_id, dict) and "$oid" in raw_id:
                normalized["id"] = str(raw_id["$oid"])
            elif raw_id is not None:
                normalized["id"] = str(raw_id)
            else:
                normalized["id"] = None

            for key, val in doc.items():
                if key == "_id":
                    continue
                if isinstance(val, dict) and "$date" in val:
                    normalized[key] = str(val["$date"])
                elif isinstance(val, (dict, list)):
                    normalized[key] = json.dumps(val, default=str)
                elif isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
                    try:
                        json.loads(val)
                        normalized[key] = val
                    except json.JSONDecodeError:
                        normalized[key] = val
                else:
                    normalized[key] = val

            return normalized, True
        except Exception as exc:
            if self.quarantine_invalid:
                self.quarantined_records.append(
                    QuarantineRecord(
                        source_id=str(doc.get("_id", "unknown")),
                        raw_payload=str(doc),
                        failure_reason=f"Transformation exception: {str(exc)}"
                    )
                )
            return {}, False

    def transform_mysql_row(
        self,
        row: Dict[str, Any],
        schema_mappings: Dict[str, ColumnMapping]
    ) -> Tuple[Dict[str, Any], bool]:
        """Transforms relational MySQL row into PostgreSQL row according to column schema."""
        transformed: Dict[str, Any] = {}
        source_id = str(row.get("id", "unknown"))

        try:
            for field_name, value in row.items():
                mapping = schema_mappings.get(field_name)
                target_col = mapping.target_column if mapping else field_name
                target_type = mapping.target_type if mapping else TargetDataType.VARCHAR

                if target_type == TargetDataType.TIMESTAMP:
                    transformed[target_col] = self.sanitize_mysql_zero_date(value)
                elif target_type == TargetDataType.BOOLEAN:
                    if value is None:
                        transformed[target_col] = None
                    else:
                        transformed[target_col] = bool(value)
                elif target_type == TargetDataType.JSONB:
                    if isinstance(value, (dict, list)):
                        transformed[target_col] = json.dumps(value, default=str)
                    elif value is None:
                        transformed[target_col] = None
                    else:
                        transformed[target_col] = str(value)
                else:
                    transformed[target_col] = value

            return transformed, True
        except Exception as exc:
            if self.quarantine_invalid:
                self.quarantined_records.append(
                    QuarantineRecord(
                        source_id=source_id,
                        raw_payload=str(row),
                        failure_reason=f"MySQL transform failure: {str(exc)}"
                    )
                )
            return {}, False
