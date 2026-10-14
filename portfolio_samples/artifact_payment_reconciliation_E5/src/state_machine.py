"""Deterministic state machine governing payment lifecycles and resolving out-of-order webhooks.
Zero em dashes policy strictly enforced.
"""
from typing import Dict, Set, Tuple, Optional
from decimal import Decimal
from src.models import PaymentStatus, PaymentEvent, ReconciliationDiscrepancy, GatewayType


class PaymentStateMachine:
    """Manages valid state transitions and detects status discrepancies."""

    VALID_TRANSITIONS: Dict[PaymentStatus, Set[PaymentStatus]] = {
        PaymentStatus.INITIATED: {PaymentStatus.AUTHORIZED, PaymentStatus.CAPTURED, PaymentStatus.FAILED},
        PaymentStatus.AUTHORIZED: {PaymentStatus.CAPTURED, PaymentStatus.FAILED},
        PaymentStatus.CAPTURED: {PaymentStatus.REFUNDED},
        PaymentStatus.FAILED: set(),
        PaymentStatus.REFUNDED: set(),
        # Order-level transitions (PENDING -> PAID / FAILED / REFUNDED)
        PaymentStatus.PENDING: {PaymentStatus.PAID, PaymentStatus.FAILED, PaymentStatus.REFUNDED},
        PaymentStatus.PAID: {PaymentStatus.REFUNDED},
    }

    def __init__(self):
        self.out_of_order_recoveries: int = 0
        self.discrepancies_detected: list[ReconciliationDiscrepancy] = []

    def can_transition(self, current: PaymentStatus, target: PaymentStatus) -> bool:
        """Check whether state transition is valid according to state machine rules."""
        if current == target:
            return True
        allowed = self.VALID_TRANSITIONS.get(current, set())
        return target in allowed

    def resolve_transition(self, current: PaymentStatus, incoming: PaymentStatus) -> Tuple[PaymentStatus, bool]:
        """Resolve state transition, handling out-of-order arrivals (e.g. CAPTURED before AUTHORIZED)."""
        if self.can_transition(current, incoming):
            return incoming, False

        # Out-of-order scenario: incoming is AUTHORIZED but current is already CAPTURED
        if current == PaymentStatus.CAPTURED and incoming == PaymentStatus.AUTHORIZED:
            self.out_of_order_recoveries += 1
            return current, True

        # Out-of-order scenario: incoming is PAID but current is already PAID
        if current == PaymentStatus.PAID and incoming == PaymentStatus.PENDING:
            self.out_of_order_recoveries += 1
            return current, True

        # Invalid transition detected (e.g. REFUNDED -> AUTHORIZED)
        return current, False

    def check_discrepancy(
        self,
        payment_id: str,
        gateway: GatewayType,
        internal_status: PaymentStatus,
        gateway_status: PaymentStatus,
        internal_amount: Decimal,
        gateway_amount: Decimal,
    ) -> Optional[ReconciliationDiscrepancy]:
        """Detect divergence between internal ledger and upstream gateway records."""
        reasons = []
        if internal_status != gateway_status:
            reasons.append(f"Status mismatch: internal={internal_status.value}, gateway={gateway_status.value}")
        if internal_amount != gateway_amount:
            reasons.append(f"Amount mismatch: internal={internal_amount}, gateway={gateway_amount}")

        if reasons:
            disc = ReconciliationDiscrepancy(
                payment_id=payment_id,
                gateway=gateway,
                internal_status=internal_status,
                gateway_status=gateway_status,
                internal_amount=internal_amount,
                gateway_amount=gateway_amount,
                discrepancy_reason="; ".join(reasons),
            )
            self.discrepancies_detected.append(disc)
            return disc
        return None


# Order-specific state machine alias
OrderStateMachine = PaymentStateMachine
