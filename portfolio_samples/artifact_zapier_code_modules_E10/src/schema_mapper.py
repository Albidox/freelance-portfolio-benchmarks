"""Dynamic JSON schema transformer mapping arbitrary inbound payloads to target structures.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional, Tuple, Union
import time
from datetime import datetime, timezone
from src.models import TransformerInput, TransformationResult


class SchemaMapper:
    """Dynamic declarative schema mapping engine translating unstructured or third-party JSON into target models."""

    def __init__(self):
        self.mappings_executed = 0

    @staticmethod
    def extract_path(data: Dict[str, Any], path: str, default: Any = None) -> Any:
        """Resolve dot-notated field path safely across nested dictionaries and arrays."""
        if not path:
            return default
        parts = path.split(".")
        curr: Any = data
        for part in parts:
            if isinstance(curr, dict) and part in curr:
                curr = curr[part]
            elif isinstance(curr, (list, tuple)) and part.isdigit():
                idx = int(part)
                if 0 <= idx < len(curr):
                    curr = curr[idx]
                else:
                    return default
            else:
                return default
        return curr

    def coerce_type(self, val: Any, target_type: str, default: Any = None) -> Any:
        """Cast value to requested target type with graceful fallback on parse errors."""
        if val is None:
            return default
        try:
            t = target_type.lower().strip()
            if t in ("str", "string", "text"):
                return str(val)
            if t in ("int", "integer"):
                return int(float(val))
            if t in ("float", "number", "decimal"):
                return float(val)
            if t in ("bool", "boolean"):
                if isinstance(val, bool):
                    return val
                s = str(val).lower().strip()
                return s in ("true", "1", "yes", "y", "t")
            if t in ("list", "array"):
                return list(val) if isinstance(val, (list, tuple, set)) else [val]
            if t in ("dict", "object"):
                return dict(val) if isinstance(val, dict) else default
            return val
        except (ValueError, TypeError):
            return default

    def map_schema(
        self,
        source: Dict[str, Any],
        schema_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transform source dictionary according to declarative schema specification.

        Supports two specification styles:
        1. Simple key-path mapping:
           {"target_name": "source.nested.path"}
        2. Rich field specification:
           {"target_name": {"path": "source.path", "type": "int", "default": 0, "transform": "uppercase"}}
        """
        output: Dict[str, Any] = {}

        for target_key, rule in schema_spec.items():
            if isinstance(rule, str):
                # Simple path string
                val = self.extract_path(source, rule, default=None)
                output[target_key] = val
            elif isinstance(rule, dict):
                # Rich configuration dict
                source_path = rule.get("path", target_key)
                default_val = rule.get("default", None)
                val = self.extract_path(source, source_path, default=default_val)

                # Type coercion
                if "type" in rule and val is not None:
                    val = self.coerce_type(val, rule["type"], default=default_val)

                # String transformations
                if isinstance(val, str):
                    transform_action = rule.get("transform", "").lower()
                    if transform_action == "uppercase":
                        val = val.upper()
                    elif transform_action == "lowercase":
                        val = val.lower()
                    elif transform_action == "strip":
                        val = val.strip()

                output[target_key] = val
            elif callable(rule):
                # Lambda or function mapping
                try:
                    output[target_key] = rule(source)
                except Exception:
                    output[target_key] = None
            else:
                output[target_key] = rule

        self.mappings_executed += 1
        return output

    def validate_schema(
        self,
        payload: Dict[str, Any],
        required_fields: List[str]
    ) -> Tuple[bool, List[str]]:
        """Verify that payload contains all non-null required fields."""
        missing = [f for f in required_fields if payload.get(f) is None]
        return (len(missing) == 0, missing)

    def process_bundle(self, input_bundle: TransformerInput) -> TransformationResult:
        """Execute schema transformation on a TransformerInput bundle."""
        t0 = time.perf_counter()
        if not input_bundle.target_schema:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            return TransformationResult(
                transformed_payload=input_bundle.input_payload,
                record_count=len(input_bundle.input_payload),
                execution_time_ms=round(duration_ms, 3),
                success=True,
                error=None
            )

        try:
            mapped = self.map_schema(input_bundle.input_payload, input_bundle.target_schema)
            duration_ms = (time.perf_counter() - t0) * 1000.0
            return TransformationResult(
                transformed_payload=mapped,
                record_count=len(mapped),
                execution_time_ms=round(duration_ms, 3),
                success=True,
                error=None
            )
        except Exception as ex:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            return TransformationResult(
                transformed_payload={},
                record_count=0,
                execution_time_ms=round(duration_ms, 3),
                success=False,
                error=str(ex)
            )
