"""Portfolio risk manager, drawdown limits, and emergency kill-switch."""
from typing import Tuple, Optional
from decimal import Decimal
from src.models import RiskProfile, TradingViewAlert, OrderSide

class RiskManager:
    def __init__(self, profile: RiskProfile):
        self.profile = profile
        self.rejected_trades = 0

    def trigger_kill_switch(self, reason: str) -> None:
        """Activate emergency kill switch to halt all trade processing immediately."""
        self.profile.emergency_kill_switch_active = True

    def reset_kill_switch(self) -> None:
        """Deactivate emergency kill switch."""
        self.profile.emergency_kill_switch_active = False

    def validate_risk_boundaries(self, alert: TradingViewAlert) -> Tuple[bool, str]:
        """Verify Stop-Loss and Take-Profit logical directions relative to entry price."""
        if alert.price is None:
            return True, "Market order without explicit reference price"

        entry = alert.price
        if alert.action == OrderSide.BUY:
            if alert.stop_loss is not None and alert.stop_loss >= entry:
                return False, f"Inverted SL for BUY: stop_loss ({alert.stop_loss}) must be strictly less than entry price ({entry})"
            if alert.take_profit is not None and alert.take_profit <= entry:
                return False, f"Inverted TP for BUY: take_profit ({alert.take_profit}) must be strictly greater than entry price ({entry})"
        elif alert.action == OrderSide.SELL:
            if alert.stop_loss is not None and alert.stop_loss <= entry:
                return False, f"Inverted SL for SELL: stop_loss ({alert.stop_loss}) must be strictly greater than entry price ({entry})"
            if alert.take_profit is not None and alert.take_profit >= entry:
                return False, f"Inverted TP for SELL: take_profit ({alert.take_profit}) must be strictly less than entry price ({entry})"

        return True, "Boundaries verified"

    def check_trade_allowed(self, alert: TradingViewAlert, estimated_price: Decimal) -> Tuple[bool, str]:
        """Evaluate trade against active kill switch, drawdown limits, and position size."""
        if self.profile.emergency_kill_switch_active:
            self.rejected_trades += 1
            return False, "Emergency kill switch is ACTIVE: all order executions blocked"

        notional_value = alert.quantity * estimated_price
        if notional_value > self.profile.max_position_size_usd:
            self.rejected_trades += 1
            return False, f"Trade notional {notional_value} exceeds max position size {self.profile.max_position_size_usd}"

        if self.profile.current_daily_loss_usd >= self.profile.daily_loss_limit_usd:
            self.rejected_trades += 1
            return False, f"Daily loss limit reached: current loss {self.profile.current_daily_loss_usd} >= limit {self.profile.daily_loss_limit_usd}"

        return True, "Trade complies with risk limits"

    def validate_slippage(self, expected_price: Decimal, fill_price: Decimal, side: OrderSide, max_slippage_bps: int = 50) -> Tuple[bool, float, str]:
        """Verify execution slippage does not exceed maximum allowable threshold."""
        if expected_price == Decimal("0.0"):
            return True, 0.0, "Zero expected price"
        if side == OrderSide.BUY:
            diff = fill_price - expected_price
        else:
            diff = expected_price - fill_price
        bps = float((diff / expected_price) * Decimal("10000.0"))
        actual_bps = max(0.0, bps)
        if actual_bps > max_slippage_bps:
            return False, actual_bps, f"Execution aborted: slippage {actual_bps:.1f} bps exceeds limit {max_slippage_bps} bps"
        return True, actual_bps, f"Slippage {actual_bps:.1f} bps within limit {max_slippage_bps} bps"
