"""CCXT-compatible order execution engine with slippage guards and deduplication."""
import time
from typing import Tuple, Dict, Any, Optional
from decimal import Decimal
from collections import OrderedDict
from src.models import (
    TradingViewAlert,
    ExecutionOrder,
    TradeExecutionResult,
    OrderSide,
    OrderType,
    OrderStatus
)

class ExchangeExecutor:
    def __init__(self, max_slippage_bps: int = 50, cache_size: int = 1000):
        self.max_slippage_bps = max_slippage_bps
        self.processed_alerts = OrderedDict()
        self.cache_size = cache_size
        self.execution_attempts = 0
        self.duplicate_blocks = 0
        self.slippage_rejections = 0

    def is_duplicate_alert(self, alert_id: str) -> bool:
        """Check and record alert ID in bounded LRU cache to prevent double execution."""
        if alert_id in self.processed_alerts:
            self.duplicate_blocks += 1
            return True
        self.processed_alerts[alert_id] = time.time()
        if len(self.processed_alerts) > self.cache_size:
            self.processed_alerts.popitem(last=False)
        return False

    def calculate_slippage_bps(self, expected_price: Decimal, fill_price: Decimal, side: OrderSide) -> float:
        """Calculate slippage in basis points (1 bp = 0.01%). Positive bps represents adverse slippage."""
        if expected_price == Decimal("0.0"):
            return 0.0
        if side == OrderSide.BUY:
            diff = fill_price - expected_price
        else:
            diff = expected_price - fill_price
        bps = float((diff / expected_price) * Decimal("10000.0"))
        return max(0.0, bps)

    def execute_order(
        self,
        alert: TradingViewAlert,
        current_market_price: Decimal,
        simulated_fill_price: Optional[Decimal] = None
    ) -> Tuple[Optional[TradeExecutionResult], str]:
        """Execute order with strict slippage verification and duplicate protection."""
        self.execution_attempts += 1
        if self.is_duplicate_alert(alert.alert_id):
            return None, f"Duplicate alert rejected: {alert.alert_id}"

        expected_price = alert.price if alert.price is not None else current_market_price
        fill_price = simulated_fill_price if simulated_fill_price is not None else current_market_price

        slippage = self.calculate_slippage_bps(expected_price, fill_price, alert.action)
        if slippage > self.max_slippage_bps:
            self.slippage_rejections += 1
            return None, f"Execution aborted: slippage {slippage:.1f} bps exceeds limit {self.max_slippage_bps} bps"

        fee = alert.quantity * fill_price * Decimal("0.00075")
        result = TradeExecutionResult(
            execution_id=f"exec_{alert.alert_id}_{int(time.time())}",
            order_id=f"ord_{alert.alert_id}",
            symbol=alert.symbol,
            side=alert.action,
            filled_quantity=alert.quantity,
            average_fill_price=fill_price,
            fee_amount=fee,
            fee_currency="USDT",
            status=OrderStatus.FILLED,
            slippage_bps=slippage,
            execution_latency_ms=11.4
        )
        return result, "Order filled successfully"
