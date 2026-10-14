"""Data models and validation contracts for Payment Webhook Reconciliation.
Zero em dashes policy strictly enforced.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from enum import Enum
from decimal import Decimal
import time
from datetime import datetime, timezone


class GatewayType(str, Enum):
    STRIPE = "stripe"
    RAZORPAY = "razorpay"


class PaymentStatus(str, Enum):
    INITIATED = "INITIATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    PENDING = "PENDING"
    PAID = "PAID"


@dataclass
class WebhookPayload:
    gateway: GatewayType
    event_id: str
    event_type: str
    raw_payload: str
    signature_header: str
    timestamp: int
    received_at: float = field(default_factory=time.time)


@dataclass
class PaymentEvent:
    gateway: GatewayType
    event_id: str
    payment_id: str
    order_id: Optional[str]
    amount: Decimal
    currency: str
    status: PaymentStatus
    fee: Decimal = Decimal("0.00")
    tax: Decimal = Decimal("0.00")
    error_code: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gateway": self.gateway.value,
            "event_id": self.event_id,
            "payment_id": self.payment_id,
            "order_id": self.order_id,
            "amount": float(self.amount),
            "currency": self.currency,
            "status": self.status.value,
            "fee": float(self.fee),
            "tax": float(self.tax),
            "error_code": self.error_code,
            "created_at": self.created_at,
        }


@dataclass
class OrderRecord:
    order_id: str
    customer_id: str
    amount: Decimal
    currency: str
    status: str = "PENDING"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payment_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "amount": float(self.amount),
            "currency": self.currency,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "payment_ids": self.payment_ids,
            "metadata": self.metadata,
        }


@dataclass
class ReconciliationDiscrepancy:
    payment_id: str
    gateway: GatewayType
    internal_status: PaymentStatus
    gateway_status: PaymentStatus
    internal_amount: Decimal
    gateway_amount: Decimal
    discrepancy_reason: str
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ReconciliationResult:
    total_scanned: int = 0
    matched_count: int = 0
    discrepancy_count: int = 0
    corrected_count: int = 0
    discrepancies: List[ReconciliationDiscrepancy] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    reconciliation_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
