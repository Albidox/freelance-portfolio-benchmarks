"""Bidirectional delta change detector comparing snapshots via SHA-256 fingerprints.
Zero em dash policy enforced.
"""
from typing import List, Dict, Any, Tuple
from src.models import SyncRecordItem, ChangeDelta, ChangeType


class TwoWaySyncEngine:
    def __init__(self):
        pass

    def compute_deltas(
        self,
        source_name: str,
        current_records: List[SyncRecordItem],
        cached_snapshots: Dict[str, str]
    ) -> List[ChangeDelta]:
        """Compares current state with cached snapshot fingerprints to compute deltas."""
        deltas: List[ChangeDelta] = []
        current_ids = set()

        for rec in current_records:
            e_id = rec.entity_id
            current_ids.add(e_id)
            current_hash = rec.calculate_fingerprint()

            if e_id not in cached_snapshots:
                # New record added
                deltas.append(
                    ChangeDelta(
                        entity_id=e_id,
                        change_type=ChangeType.ADDED,
                        source=source_name,
                        new_data=rec.fields
                    )
                )
            elif cached_snapshots[e_id] != current_hash:
                # Existing record updated
                deltas.append(
                    ChangeDelta(
                        entity_id=e_id,
                        change_type=ChangeType.UPDATED,
                        source=source_name,
                        new_data=rec.fields
                    )
                )
            else:
                # Record unchanged
                deltas.append(
                    ChangeDelta(
                        entity_id=e_id,
                        change_type=ChangeType.UNCHANGED,
                        source=source_name,
                        new_data=rec.fields
                    )
                )

        # Detect deleted records
        for cached_id in cached_snapshots:
            if cached_id not in current_ids:
                deltas.append(
                    ChangeDelta(
                        entity_id=cached_id,
                        change_type=ChangeType.DELETED,
                        source=source_name
                    )
                )

        return deltas
