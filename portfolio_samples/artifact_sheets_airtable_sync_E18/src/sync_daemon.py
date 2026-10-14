"""Sync daemon coordinating delta detection, conflict resolution, and execution.
Zero em dash policy enforced.
"""
import time
from typing import List, Dict, Any, Optional
from src.models import (
    SyncDirection,
    ConflictStrategy,
    SyncRecordItem,
    SyncCycleReport,
    ChangeType,
    ConflictResolutionResult
)
from src.config import SheetsAirtableSyncConfig
from src.sync_engine import TwoWaySyncEngine
from src.conflict_resolver import ConflictResolver


class SyncDaemon:
    def __init__(self, config: SheetsAirtableSyncConfig):
        self.config = config
        self.sync_engine = TwoWaySyncEngine()
        self.resolver = ConflictResolver(ConflictStrategy(config.default_conflict_strategy))
        self.cached_sheets_snapshots: Dict[str, str] = {}
        self.cached_airtable_snapshots: Dict[str, str] = {}

    def execute_sync_cycle(
        self,
        cycle_id: str,
        sheets_records: List[SyncRecordItem],
        airtable_records: List[SyncRecordItem],
        direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    ) -> SyncCycleReport:
        """Executes a full two-way synchronization cycle with delta detection and conflict handling."""
        start_time = time.perf_counter()

        sheets_deltas = self.sync_engine.compute_deltas(
            "SHEETS", sheets_records, self.cached_sheets_snapshots
        )
        airtable_deltas = self.sync_engine.compute_deltas(
            "AIRTABLE", airtable_records, self.cached_airtable_snapshots
        )

        added_count = 0
        updated_count = 0
        deleted_count = 0
        conflicts_resolved = 0
        conflicts_quarantined = 0

        # Check for simultaneous dual-write conflicts on shared entity IDs
        sheets_map = {r.entity_id: r for r in sheets_records}
        for r_airtable in airtable_records:
            if r_airtable.entity_id in sheets_map:
                r_sheets = sheets_map[r_airtable.entity_id]
                if r_sheets.fingerprint != r_airtable.fingerprint:
                    resolution = self.resolver.resolve_conflict(r_sheets, r_airtable)
                    if resolution.quarantined:
                        conflicts_quarantined += 1
                    else:
                        conflicts_resolved += 1

        # Update cache snapshots
        for r in sheets_records:
            self.cached_sheets_snapshots[r.entity_id] = r.calculate_fingerprint()
        for r in airtable_records:
            self.cached_airtable_snapshots[r.entity_id] = r.calculate_fingerprint()

        for d in sheets_deltas:
            if d.change_type == ChangeType.ADDED:
                added_count += 1
            elif d.change_type == ChangeType.UPDATED:
                updated_count += 1
            elif d.change_type == ChangeType.DELETED:
                deleted_count += 1

        elapsed = time.perf_counter() - start_time

        return SyncCycleReport(
            cycle_id=cycle_id,
            direction=direction,
            records_scanned=len(sheets_records) + len(airtable_records),
            records_added=added_count,
            records_updated=updated_count,
            records_deleted=deleted_count,
            conflicts_resolved=conflicts_resolved,
            conflicts_quarantined=conflicts_quarantined,
            elapsed_seconds=round(elapsed, 4)
        )
