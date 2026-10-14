"""Pure standard library recursive dictionary/array flattener with delimiter customization.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Union, Optional
import time
from src.models import TransformerInput, TransformationResult


class NestedFlattener:
    """Recursive nested structure flattener with customizable delimiters and unflattening support."""

    def __init__(self, default_sep: str = "_"):
        self.default_sep = default_sep

    def flatten(
        self,
        d: Dict[str, Any],
        parent_key: str = "",
        sep: Optional[str] = None
    ) -> Dict[str, Any]:
        """Flatten deeply nested dictionary and array structures into a single-level key-value map."""
        delimiter = sep if sep is not None else self.default_sep
        items: List[tuple] = []

        if not isinstance(d, dict):
            return {parent_key: d} if parent_key else {}

        for k, v in d.items():
            new_key = f"{parent_key}{delimiter}{k}" if parent_key else str(k)
            if isinstance(v, dict):
                items.extend(self.flatten(v, new_key, sep=delimiter).items())
            elif isinstance(v, (list, tuple)):
                for idx, item in enumerate(v):
                    list_key = f"{new_key}{delimiter}{idx}"
                    if isinstance(item, dict):
                        items.extend(self.flatten(item, list_key, sep=delimiter).items())
                    elif isinstance(item, (list, tuple)):
                        items.extend(self.flatten({str(i): val for i, val in enumerate(item)}, list_key, sep=delimiter).items())
                    else:
                        items.append((list_key, item))
            else:
                items.append((new_key, v))
        return dict(items)

    def unflatten(
        self,
        flat_dict: Dict[str, Any],
        sep: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reconstruct nested dictionary from flattened key-value pairs."""
        delimiter = sep if sep is not None else self.default_sep
        result: Dict[str, Any] = {}

        for composite_key, value in flat_dict.items():
            parts = str(composite_key).split(delimiter)
            curr = result
            for i, part in enumerate(parts[:-1]):
                if part not in curr:
                    curr[part] = {}
                elif not isinstance(curr[part], dict):
                    curr[part] = {"_val": curr[part]}
                curr = curr[part]
            curr[parts[-1]] = value
        return result

    def process_bundle(self, input_bundle: TransformerInput) -> TransformationResult:
        """Process a structured TransformerInput bundle and return a TransformationResult."""
        t0 = time.perf_counter()
        try:
            flattened = self.flatten(
                input_bundle.input_payload,
                sep=input_bundle.delimiter
            )
            duration_ms = (time.perf_counter() - t0) * 1000.0
            return TransformationResult(
                transformed_payload=flattened,
                record_count=len(flattened),
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



