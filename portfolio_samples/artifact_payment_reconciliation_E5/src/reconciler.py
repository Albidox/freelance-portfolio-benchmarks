"""Payment drop-off and mismatch resolution engine with automated ledger correction.
Zero em dashes policy strictly enforced.
"""
import time
from typing import List, Dict, Any, Optional
from decimal import Decimal
from src.models import (
    GatewayType,
    PaymentStatus,
    PaymentEvent,
    OrderRecord,
    ReconciliationDiscrepancy,
    ReconciliationResult,
)
from src.state_machine import PaymentStateMachine
from src.db import LedgerStorageEngine
from src.config import PaymentReconcilerConfig


class PaymentReconciler:
    """Enterprise payment drop-off and mismatch resolution engine."""

    def __init__(
        self,
        db_engine: LedgerStorageEngine,
        state_machine: Optional[PaymentStateMachine] = None,
        config: Optional[PaymentReconcilerConfig] = None,
    ):
        self.db = db_engine
        self.sm = state_machine or PaymentStateMachine()
        self.config = config or PaymentReconcilerConfig()

    def reconcile_transaction(
        self,
        upstream_event: PaymentEvent,
        internal_order: Optional[Dict[str, Any]],
        internal_ledger: Optional[Dict[str, Any]],
    ) -> Optional[ReconciliationDiscrepancy]:
        """Detect and return any discrepancy between gateway settlement and internal state."""
        internal_status = PaymentStatus.INITIATED
        internal_amount = upstream_event.amount

        if internal_ledger:
            try:
                internal_status = PaymentStatus(internal_ledger["status"])
            except ValueError:
                internal_status = PaymentStatus.INITIATED
            internal_amount = internal_ledger["amount"]
        elif internal_order:
            order_status_str = internal_order["status"]
            if order_status_str == "PAID":
                internal_status = PaymentStatus.CAPTURED
            elif order_status_str == "PENDING":
                internal_status = PaymentStatus.INITIATED
            elif order_status_str == "FAILED":
                internal_status = PaymentStatus.FAILED
            elif order_status_str == "REFUNDED":
                internal_status = PaymentStatus.REFUNDED
            internal_amount = internal_order["amount"]

        return self.sm.check_discrepancy(
            payment_id=upstream_event.payment_id,
            gateway=upstream_event.gateway,
            internal_status=internal_status,
            gateway_status=upstream_event.status,
            internal_amount=internal_amount,
            gateway_amount=upstream_event.amount,
        )

    def reconcile_batch(
        self, upstream_events: List[PaymentEvent]
    ) -> ReconciliationResult:
        """Process a batch of gateway events, resolve discrepancies, and apply automated ledger corrections."""
        start_time = time.perf_counter()
        result = ReconciliationResult()
        result.total_scanned = len(upstream_events)

        # Pre-fetch existing orders and ledger records for index lookup
        orders_list = self.db.fetch_orders()
        orders_by_id = {o["order_id"]: o for o in orders_list}

        ledger_list = self.db.fetch_ledger_records()
        ledger_by_payment_id = {l["payment_id"]: l for l in ledger_list}

        discrepancies: List[ReconciliationDiscrepancy] = []
        corrections_applied = 0

        for event in upstream_events:
            order = orders_by_id.get(event.order_id) if event.order_id else None
            ledger_entry = ledger_by_payment_id.get(event.payment_id)

            disc = self.reconcile_transaction(event, order, ledger_entry)
            if disc:
                discrepancies.append(disc)
                # Apply automated ledger correction
                note = f"Automated reconciliation: resolved {disc.discrepancy_reason}"
                self.db.record_event_and_update_ledger(event)
                if event.order_id:
                    new_order_status = "PAID" if event.status == PaymentStatus.CAPTURED else event.status.value
                    corrected_order = OrderRecord(
                        order_id=event.order_id,
                        customer_id=order["customer_id"] if order else "unknown_cust",
                        amount=event.amount,
                        currency=event.currency,
                        status=new_order_status,
                    )
                    self.db.upsert_order(corrected_order)
                self.db.record_audit(event.payment_id, note, resolved=True)
                corrections_applied += 1
            else:
                result.matched_count += 1

        elapsed = time.perf_counter() - start_time
        result.discrepancy_count = len(discrepancies)
        result.corrected_count = corrections_applied
        result.discrepancies = discrepancies
        result.elapsed_seconds = elapsed
        return result
