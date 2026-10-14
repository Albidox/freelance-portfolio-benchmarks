"""SHA-256 cryptographic reconciliation verifier verifying 100% data fidelity.
Strict zero em dash policy enforced.
"""
import hashlib
import json
import time
from typing import List, Dict, Any
from src.models import ReconciliationReport


class ReconciliationVerifier:
    """Performs row-level and aggregate Merkle root cryptographic reconciliation."""

    def __init__(self):
        pass

    def compute_record_hash(self, record: Dict[str, Any]) -> str:
        """Computes deterministic SHA-256 hash for a single row."""
        serialized = json.dumps(record, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def compute_dataset_root_hash(self, records: List[Dict[str, Any]]) -> str:
        """Generates cumulative Merkle-like root hash across an entire dataset."""
        if not records:
            return hashlib.sha256(b"EMPTY_DATASET").hexdigest()

        individual_hashes = [self.compute_record_hash(r) for r in records]
        individual_hashes.sort()
        combined = "".join(individual_hashes)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def reconcile_datasets(
        self,
        table_name: str,
        source_records: List[Dict[str, Any]],
        target_records: List[Dict[str, Any]]
    ) -> ReconciliationReport:
        """Performs row-by-row and aggregate reconciliation between source and target."""
        start_time = time.perf_counter()

        source_count = len(source_records)
        target_count = len(target_records)

        source_root = self.compute_dataset_root_hash(source_records)
        target_root = self.compute_dataset_root_hash(target_records)

        source_map = {str(r.get("id")): self.compute_record_hash(r) for r in source_records}
        target_map = {str(r.get("id")): self.compute_record_hash(r) for r in target_records}

        missing_in_target = 0
        data_mismatches = 0

        for s_id, s_hash in source_map.items():
            if s_id not in target_map:
                missing_in_target += 1
            elif target_map[s_id] != s_hash:
                data_mismatches += 1

        is_verified = (source_count == target_count) and (source_root == target_root) and (data_mismatches == 0)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return ReconciliationReport(
            table_name=table_name,
            source_total_count=source_count,
            target_total_count=target_count,
            source_checksum_root=source_root,
            target_checksum_root=target_root,
            missing_in_target=missing_in_target,
            data_mismatches=data_mismatches,
            is_verified=is_verified,
            reconciliation_time_ms=round(elapsed_ms, 2)
        )
