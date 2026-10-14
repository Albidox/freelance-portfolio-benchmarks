"""Data contracts, enums, and dataclass models for TradingView Execution Bot."""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
from decimal import Decimal
from datetime import datetime, timezone

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

@dataclass
class TradingViewAlert:
    alert_id: str
    symbol: str
    action: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    passphrase: Optional[str] = None
    timestamp: int = field(default_factory=lambda: int(datetime.now(timezone.utc).timestamp()))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        """Validate alert invariants: positive quantity and valid symbol."""
        if not self.alert_id or not self.symbol:
            return False
        if self.quantity <= Decimal("0.0"):
            return False
        if self.price is not None and self.price <= Decimal("0.0"):
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "symbol": self.symbol,
            "action": self.action.value,
            "order_type": self.order_type.value,
            "quantity": float(self.quantity),
            "price": float(self.price) if self.price is not None else None,
            "stop_loss": float(self.stop_loss) if self.stop_loss is not None else None,
            "take_profit": float(self.take_profit) if self.take_profit is not None else None,
            "passphrase": self.passphrase,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

# Domain alias
SignalAlert = TradingViewAlert

@dataclass
class ExecutionOrder:
    order_id: str
    alert_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Optional[Decimal]
    max_slippage_bps: int
    status: OrderStatus = OrderStatus.PENDING
    submitted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# Domain alias
OrderRequest = ExecutionOrder

@dataclass
class TradeExecutionResult:
    execution_id: str
    order_id: str
    symbol: str
    side: OrderSide
    filled_quantity: Decimal
    average_fill_price: Decimal
    fee_amount: Decimal
    fee_currency: str
    status: OrderStatus
    slippage_bps: float
    execution_latency_ms: float
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# Domain alias
ExecutionReceipt = TradeExecutionResult

@dataclass
class PositionState:
    symbol: str
    side: OrderSide
    quantity: Decimal = Decimal("0.0")
    entry_price: Decimal = Decimal("0.0")
    current_price: Decimal = Decimal("0.0")
    unrealized_pnl: Decimal = Decimal("0.0")
    realized_pnl: Decimal = Decimal("0.0")
    leverage: int = 1
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class RiskProfile:
    max_account_drawdown_pct: float = 5.0
    max_position_size_usd: Decimal = Decimal("10000.00")
    max_leverage: int = 10
    daily_loss_limit_usd: Decimal = Decimal("500.00")
    current_daily_loss_usd: Decimal = Decimal("0.00")
    emergency_kill_switch_active: bool = False
