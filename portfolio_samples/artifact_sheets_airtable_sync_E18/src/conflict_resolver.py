"""Deterministic conflict resolver handling simultaneous dual-write edits.
Zero em dash policy enforced.
"""
from typing import Dict, Any, Optional
from src.models import SyncRecordItem, ConflictStrategy, ConflictResolutionResult


class ConflictResolver:
    def __init__(self, default_strategy: ConflictStrategy = ConflictStrategy.TIMESTAMP_PRECEDENCE):
        self.default_strategy = default_strategy

    def resolve_conflict(
        self,
        sheets_record: SyncRecordItem,
        airtable_record: SyncRecordItem,
        strategy: Optional[ConflictStrategy] = None
    ) -> ConflictResolutionResult:
        chosen_strategy = strategy or self.default_strategy
        entity_id = sheets_record.entity_id

        if chosen_strategy == ConflictStrategy.SHEETS_WINS:
            return ConflictResolutionResult(
                entity_id=entity_id,
                strategy_applied=chosen_strategy,
                resolved_fields=sheets_record.fields,
                winning_source="SHEETS"
            )

        if chosen_strategy == ConflictStrategy.AIRTABLE_WINS:
            return ConflictResolutionResult(
                entity_id=entity_id,
                strategy_applied=chosen_strategy,
                resolved_fields=airtable_record.fields,
                winning_source="AIRTABLE"
            )

        if chosen_strategy == ConflictStrategy.TIMESTAMP_PRECEDENCE:
            sheets_ts = sheets_record.last_modified
            airtable_ts = airtable_record.last_modified
            if airtable_ts > sheets_ts:
                return ConflictResolutionResult(
                    entity_id=entity_id,
                    strategy_applied=chosen_strategy,
                    resolved_fields=airtable_record.fields,
                    winning_source="AIRTABLE"
                )
            else:
                return ConflictResolutionResult(
                    entity_id=entity_id,
                    strategy_applied=chosen_strategy,
                    resolved_fields=sheets_record.fields,
                    winning_source="SHEETS"
                )

        if chosen_strategy == ConflictStrategy.FIELD_LEVEL_MERGE:
            # Non-overlapping field merge: preserves formulas from sheets, new attributes from airtable
            merged: Dict[str, Any] = {}
            merged.update(sheets_record.fields)
            for k, v in airtable_record.fields.items():
                if k not in sheets_record.formula_fields:
                    merged[k] = v
            return ConflictResolutionResult(
                entity_id=entity_id,
                strategy_applied=chosen_strategy,
                resolved_fields=merged,
                winning_source="MERGED"
            )

        # Fallback quarantine
        return ConflictResolutionResult(
            entity_id=entity_id,
            strategy_applied=chosen_strategy,
            resolved_fields={},
            winning_source="NONE",
            quarantined=True,
            quarantine_reason=f"Unknown conflict strategy: {chosen_strategy}"
        )
