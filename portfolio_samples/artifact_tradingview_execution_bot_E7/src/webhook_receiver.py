"""Cryptographic signature verifier, IP whitelist validator, and alert receiver."""
import hmac
import hashlib
import time
import json
from typing import Tuple, Dict, Any, Optional
from decimal import Decimal
from src.models import TradingViewAlert, OrderSide, OrderType
from src.config import TradingBotConfig

class WebhookReceiver:
    def __init__(self, config: TradingBotConfig):
        self.config = config
        self.replays_detected = 0
        self.unauthorized_ips_blocked = 0
        self.tampered_payloads_blocked = 0

    def verify_ip(self, remote_ip: str) -> bool:
        """Verify whether remote IP matches allowed TradingView IP whitelist."""
        if not remote_ip:
            self.unauthorized_ips_blocked += 1
            return False
        if remote_ip in self.config.allowed_tradingview_ips:
            return True
        self.unauthorized_ips_blocked += 1
        return False

    def verify_hmac_signature(self, payload: str, signature_header: str) -> bool:
        """Verify HMAC-SHA256 signature using constant-time comparison."""
        if not signature_header or not payload:
            self.tampered_payloads_blocked += 1
            return False
        computed = hmac.new(
            self.config.webhook_secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if hmac.compare_digest(computed, signature_header):
            return True
        self.tampered_payloads_blocked += 1
        return False

    def verify_passphrase(self, payload_passphrase: Optional[str]) -> bool:
        """Verify alert body passphrase against configured secret."""
        if not payload_passphrase:
            return False
        return hmac.compare_digest(payload_passphrase, self.config.webhook_passphrase)

    def check_timestamp_freshness(self, alert_timestamp: int, max_drift_seconds: int = 60, current_time: Optional[int] = None) -> Tuple[bool, str]:
        """Anti-replay guard checking alert timestamp vs current server epoch."""
        now = current_time if current_time is not None else int(time.time())
        diff = now - alert_timestamp
        if diff > max_drift_seconds:
            self.replays_detected += 1
            return False, f"Alert timestamp expired: {diff}s ago (max allowed {max_drift_seconds}s)"
        if diff < -10:
            self.replays_detected += 1
            return False, f"Alert timestamp from future: {abs(diff)}s in future"
        return True, "Timestamp valid"

    def parse_alert_json(self, raw_json: str) -> Tuple[Optional[TradingViewAlert], str]:
        """Parse raw incoming JSON string into validated TradingViewAlert model."""
        try:
            data = json.loads(raw_json)
        except Exception as e:
            return None, f"JSON parse failure: {str(e)}"

        alert_id = str(data.get("alert_id", data.get("id", "")))
        symbol = str(data.get("symbol", data.get("ticker", "")))
        action_raw = str(data.get("action", data.get("side", ""))).upper()
        order_type_raw = str(data.get("order_type", data.get("type", "MARKET"))).upper()

        if action_raw not in OrderSide.__members__:
            return None, f"Invalid order side: {action_raw}"
        if order_type_raw not in OrderType.__members__:
            return None, f"Invalid order type: {order_type_raw}"

        try:
            quantity = Decimal(str(data.get("quantity", data.get("contracts", data.get("volume", 0)))))
        except Exception:
            return None, "Invalid quantity format"

        price = None
        if "price" in data and data["price"] is not None:
            try:
                price = Decimal(str(data["price"]))
            except Exception:
                return None, "Invalid price format"

        stop_loss = None
        if "stop_loss" in data and data["stop_loss"] is not None:
            try:
                stop_loss = Decimal(str(data["stop_loss"]))
            except Exception:
                pass

        take_profit = None
        if "take_profit" in data and data["take_profit"] is not None:
            try:
                take_profit = Decimal(str(data["take_profit"]))
            except Exception:
                pass

        passphrase = data.get("passphrase")
        timestamp = int(data.get("timestamp", int(time.time())))

        alert = TradingViewAlert(
            alert_id=alert_id,
            symbol=symbol,
            action=OrderSide[action_raw],
            order_type=OrderType[order_type_raw],
            quantity=quantity,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            passphrase=passphrase,
            timestamp=timestamp,
            metadata=data.get("metadata", {})
        )

        if not alert.validate():
            return None, "Alert validation failed: non-positive quantity or empty symbol"
        return alert, "Success"
