"""Signal parser, attribute normalizer, and risk boundary validator."""
from typing import Tuple, Dict, Any, Optional
from decimal import Decimal
from src.models import TradingViewAlert, OrderSide

class SignalValidator:
    def __init__(self):
        self.normalized_signals_count = 0
        self.boundary_violations_count = 0

    def normalize_symbol(self, raw_symbol: str) -> str:
        """Normalize symbol formats (e.g. 'btcusdt', 'BTC_USDT' -> 'BTC/USDT')."""
        s = raw_symbol.strip().upper()
        if "/" in s:
            return s
        if "_" in s:
            return s.replace("_", "/")
        if s.endswith("USDT") and len(s) > 4:
            base = s[:-4]
            return f"{base}/USDT"
        if s.endswith("USD") and len(s) > 3:
            base = s[:-3]
            return f"{base}/USD"
        return s

    def validate_risk_boundaries(self, alert: TradingViewAlert) -> Tuple[bool, str]:
        """Verify Stop-Loss and Take-Profit logical directions relative to entry price."""
        if alert.price is None:
            return True, "Market order without explicit reference price"

        entry = alert.price
        if alert.action == OrderSide.BUY:
            if alert.stop_loss is not None and alert.stop_loss >= entry:
                self.boundary_violations_count += 1
                return False, f"Inverted SL for BUY: stop_loss ({alert.stop_loss}) must be strictly less than entry price ({entry})"
            if alert.take_profit is not None and alert.take_profit <= entry:
                self.boundary_violations_count += 1
                return False, f"Inverted TP for BUY: take_profit ({alert.take_profit}) must be strictly greater than entry price ({entry})"
        elif alert.action == OrderSide.SELL:
            if alert.stop_loss is not None and alert.stop_loss <= entry:
                self.boundary_violations_count += 1
                return False, f"Inverted SL for SELL: stop_loss ({alert.stop_loss}) must be strictly greater than entry price ({entry})"
            if alert.take_profit is not None and alert.take_profit >= entry:
                self.boundary_violations_count += 1
                return False, f"Inverted TP for SELL: take_profit ({alert.take_profit}) must be strictly less than entry price ({entry})"

        return True, "Boundaries verified"

    def normalize_alert(self, alert: TradingViewAlert) -> TradingViewAlert:
        """Create normalized alert with standard symbol and verified values."""
        normalized_sym = self.normalize_symbol(alert.symbol)
        alert.symbol = normalized_sym
        self.normalized_signals_count += 1
        return alert
