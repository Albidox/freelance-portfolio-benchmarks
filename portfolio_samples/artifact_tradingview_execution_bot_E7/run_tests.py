"""Standalone deterministic test harness for E7 TradingView Webhook Bot with 26 assertions.
Runs natively on Windows without Linux shell dependencies.
"""
import hmac
import hashlib
import time
import json
import tracemalloc
from decimal import Decimal
from src.models import (
    TradingViewAlert,
    ExecutionOrder,
    TradeExecutionResult,
    RiskProfile,
    OrderSide,
    OrderType,
    OrderStatus
)
from src.config import TradingBotConfig
from src.webhook_receiver import WebhookReceiver
from src.signal_validator import SignalValidator
from src.exchange_executor import ExchangeExecutor
from src.risk_manager import RiskManager
from src.storage import TradingBotStorage

def test_models_and_contracts():
    print("Testing models and contract validations...")
    alert = TradingViewAlert(
        alert_id="alt_test_01",
        symbol="BTCUSDT",
        action=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.5"),
        price=Decimal("65000.00"),
        stop_loss=Decimal("64000.00"),
        take_profit=Decimal("68000.00")
    )

    # Assertion 1: Model dictionary serialization preserves types
    d = alert.to_dict()
    assert d["alert_id"] == "alt_test_01", "Alert ID mismatch"
    assert d["action"] == "BUY", "Action enum serialization mismatch"
    assert d["quantity"] == 0.5, "Quantity float conversion mismatch"

    # Assertion 2: Enum members match expected values
    assert OrderSide.BUY.value == "BUY"
    assert OrderSide.SELL.value == "SELL"
    assert OrderType.MARKET.value == "MARKET"

    # Assertion 3: Non-positive quantity fails validation
    invalid_alert = TradingViewAlert(
        alert_id="bad_01",
        symbol="BTCUSDT",
        action=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("-1.0")
    )
    assert invalid_alert.validate() is False, "Negative quantity must fail validation"

def test_webhook_receiver_and_security():
    print("Testing cryptographic authentication and anti-replay guards...")
    cfg = TradingBotConfig()
    receiver = WebhookReceiver(cfg)

    payload = json.dumps({
        "alert_id": "tv_991",
        "symbol": "ETH/USDT",
        "action": "BUY",
        "order_type": "MARKET",
        "quantity": 2.5,
        "price": 3500.0
    })

    # Generate valid HMAC signature
    valid_sig = hmac.new(
        cfg.webhook_secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # Assertion 4: Valid HMAC signature accepted
    assert receiver.verify_hmac_signature(payload, valid_sig) is True, "Valid HMAC must be accepted"

    # Assertion 5: Tampered payload rejected
    tampered_payload = payload.replace("2.5", "25.0")
    assert receiver.verify_hmac_signature(tampered_payload, valid_sig) is False, "Tampered body must fail"

    # Assertion 6: Mismatched signature key rejected
    bad_sig = "abcdef0123456789deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    assert receiver.verify_hmac_signature(payload, bad_sig) is False, "Invalid signature must fail"

    # Assertion 7: Expired alert timestamp rejected (>60s)
    now = int(time.time())
    stale_ts = now - 120
    is_fresh, msg = receiver.check_timestamp_freshness(stale_ts, max_drift_seconds=60, current_time=now)
    assert is_fresh is False, "Stale timestamp must be rejected"
    assert "expired" in msg.lower()

    # Assertion 8: Future timestamp drift rejected (>10s)
    future_ts = now + 45
    is_fresh_fut, _ = receiver.check_timestamp_freshness(future_ts, max_drift_seconds=60, current_time=now)
    assert is_fresh_fut is False, "Future timestamp drift must be rejected"

    # Assertion 9: Allowed TradingView IP accepted
    assert receiver.verify_ip("52.89.214.238") is True, "Official TradingView IP must be accepted"

    # Assertion 10: Unauthorized remote IP rejected
    assert receiver.verify_ip("198.51.100.44") is False, "Unauthorized IP must be blocked"

def test_signal_validator_and_schema_resolution():
    print("Testing signal normalization and boundary verification...")
    validator = SignalValidator()
    cfg = TradingBotConfig()
    receiver = WebhookReceiver(cfg)

    # Dynamic schema alias resolution
    raw_aliased_json = json.dumps({
        "id": "alt_alias_01",
        "ticker": "SOLUSDT",
        "side": "BUY",
        "volume": "10.0",
        "price": "145.00"
    })
    parsed_alert, status_msg = receiver.parse_alert_json(raw_aliased_json)
    assert parsed_alert is not None, f"Parsing failed: {status_msg}"

    # Assertion 11: Schema alias maps ticker to symbol
    assert parsed_alert.symbol == "SOLUSDT", "Ticker alias resolution failed"

    # Assertion 12: Schema alias maps side to action
    assert parsed_alert.action == OrderSide.BUY, "Side alias resolution failed"

    # Assertion 13: Schema alias maps volume to quantity
    assert parsed_alert.quantity == Decimal("10.0"), "Volume alias resolution failed"

    # Assertion 14: Symbol normalization produces standard uppercase pair
    normalized_alert = validator.normalize_alert(parsed_alert)
    assert normalized_alert.symbol == "SOL/USDT", "Symbol normalization failed"

    # Assertion 15: Valid Stop-Loss / Take-Profit for BUY accepted
    buy_alert = TradingViewAlert(
        alert_id="b1", symbol="BTC/USDT", action=OrderSide.BUY,
        order_type=OrderType.LIMIT, quantity=Decimal("1.0"),
        price=Decimal("60000.00"), stop_loss=Decimal("58000.00"), take_profit=Decimal("65000.00")
    )
    ok_buy, _ = validator.validate_risk_boundaries(buy_alert)
    assert ok_buy is True, "Valid BUY boundaries failed"

    # Assertion 16: Inverted Stop-Loss rejected for BUY (SL >= Entry)
    bad_buy_sl = TradingViewAlert(
        alert_id="b2", symbol="BTC/USDT", action=OrderSide.BUY,
        order_type=OrderType.LIMIT, quantity=Decimal("1.0"),
        price=Decimal("60000.00"), stop_loss=Decimal("61000.00")
    )
    ok_bad_sl, _ = validator.validate_risk_boundaries(bad_buy_sl)
    assert ok_bad_sl is False, "Inverted BUY stop loss must be rejected"

    # Assertion 17: Inverted Take-Profit rejected for BUY (TP <= Entry)
    bad_buy_tp = TradingViewAlert(
        alert_id="b3", symbol="BTC/USDT", action=OrderSide.BUY,
        order_type=OrderType.LIMIT, quantity=Decimal("1.0"),
        price=Decimal("60000.00"), take_profit=Decimal("59000.00")
    )
    ok_bad_tp, _ = validator.validate_risk_boundaries(bad_buy_tp)
    assert ok_bad_tp is False, "Inverted BUY take profit must be rejected"

    # Assertion 18: Valid Stop-Loss / Take-Profit for SELL accepted
    sell_alert = TradingViewAlert(
        alert_id="s1", symbol="BTC/USDT", action=OrderSide.SELL,
        order_type=OrderType.LIMIT, quantity=Decimal("1.0"),
        price=Decimal("60000.00"), stop_loss=Decimal("62000.00"), take_profit=Decimal("55000.00")
    )
    ok_sell, _ = validator.validate_risk_boundaries(sell_alert)
    assert ok_sell is True, "Valid SELL boundaries failed"

    # Assertion 19: Inverted Stop-Loss rejected for SELL (SL <= Entry)
    bad_sell_sl = TradingViewAlert(
        alert_id="s2", symbol="BTC/USDT", action=OrderSide.SELL,
        order_type=OrderType.LIMIT, quantity=Decimal("1.0"),
        price=Decimal("60000.00"), stop_loss=Decimal("58000.00")
    )
    ok_bad_sell_sl, _ = validator.validate_risk_boundaries(bad_sell_sl)
    assert ok_bad_sell_sl is False, "Inverted SELL stop loss must be rejected"

def test_exchange_executor_and_slippage():
    print("Testing order execution, deduplication, and slippage controls...")
    executor = ExchangeExecutor(max_slippage_bps=50)

    alert = TradingViewAlert(
        alert_id="alt_exec_unique_100",
        symbol="BTC/USDT",
        action=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.1"),
        price=Decimal("60000.00")
    )

    # Assertion 20: In-flight alert deduplication prevents duplicate execution
    res1, msg1 = executor.execute_order(alert, current_market_price=Decimal("60000.00"))
    assert res1 is not None, f"First execution failed: {msg1}"
    res2, msg2 = executor.execute_order(alert, current_market_price=Decimal("60000.00"))
    assert res2 is None, "Duplicate alert must be rejected"
    assert "duplicate" in msg2.lower()

    # Assertion 21: Slippage within threshold (20 bps) accepted
    alert_slip_ok = TradingViewAlert(
        alert_id="alt_slip_ok_101",
        symbol="BTC/USDT",
        action=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.1"),
        price=Decimal("60000.00")
    )
    # Expected 60000, filled at 60120 -> diff 120 / 60000 = 0.0020 = 20 bps
    res_slip_ok, _ = executor.execute_order(
        alert_slip_ok,
        current_market_price=Decimal("60000.00"),
        simulated_fill_price=Decimal("60120.00")
    )
    assert res_slip_ok is not None, "20 bps slippage must be accepted"
    assert res_slip_ok.slippage_bps == 20.0

    # Assertion 22: Excessive slippage (>50 bps) rejected
    alert_slip_bad = TradingViewAlert(
        alert_id="alt_slip_bad_102",
        symbol="BTC/USDT",
        action=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.1"),
        price=Decimal("60000.00")
    )
    # Expected 60000, filled at 60400 -> diff 400 / 60000 = 66.6 bps > 50 bps
    res_slip_bad, msg_slip = executor.execute_order(
        alert_slip_bad,
        current_market_price=Decimal("60000.00"),
        simulated_fill_price=Decimal("60400.00")
    )
    assert res_slip_bad is None, "Excessive slippage must be rejected"
    assert "slippage" in msg_slip.lower()

def test_risk_manager_and_kill_switch():
    print("Testing risk manager rules and emergency kill switch...")
    profile = RiskProfile(
        max_account_drawdown_pct=5.0,
        max_position_size_usd=Decimal("5000.00"),
        daily_loss_limit_usd=Decimal("200.00"),
        current_daily_loss_usd=Decimal("0.00")
    )
    risk_mgr = RiskManager(profile)

    alert_small = TradingViewAlert(
        alert_id="r1", symbol="ETH/USDT", action=OrderSide.BUY,
        order_type=OrderType.MARKET, quantity=Decimal("1.0")
    )
    # Assertion 23: Position size exceeding maximum notional rejected
    alert_huge = TradingViewAlert(
        alert_id="r2", symbol="ETH/USDT", action=OrderSide.BUY,
        order_type=OrderType.MARKET, quantity=Decimal("5.0")
    )
    # 5.0 * 3000 = 15000 > 5000
    ok_huge, msg_huge = risk_mgr.check_trade_allowed(alert_huge, estimated_price=Decimal("3000.00"))
    assert ok_huge is False, "Oversized position must be rejected"
    assert "max position size" in msg_huge.lower()

    # Assertion 24: Exceeded daily loss limit blocks new trades
    profile.current_daily_loss_usd = Decimal("250.00")
    ok_loss, msg_loss = risk_mgr.check_trade_allowed(alert_small, estimated_price=Decimal("3000.00"))
    assert ok_loss is False, "Daily loss exceeded must block trade"
    assert "daily loss limit" in msg_loss.lower()

    # Assertion 25: Emergency kill switch halts all trade execution
    profile.current_daily_loss_usd = Decimal("0.00")
    risk_mgr.trigger_kill_switch("High market volatility breaker")
    ok_kill, msg_kill = risk_mgr.check_trade_allowed(alert_small, estimated_price=Decimal("3000.00"))
    assert ok_kill is False, "Kill switch active must reject trade"
    assert "kill switch is active" in msg_kill.lower()

def main():
    print("=" * 70)
    print("STARTING E7 TRADINGVIEW WEBHOOK EXECUTION BOT VERIFICATION SUITE")
    print("=" * 70)
    tracemalloc.start()

    test_models_and_contracts()
    test_webhook_receiver_and_security()
    test_signal_validator_and_schema_resolution()
    test_exchange_executor_and_slippage()
    test_risk_manager_and_kill_switch()

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak_mem / (1024 * 1024)
    print(f"Memory Diagnostics: Peak memory consumed: {peak_mb:.2f} MB")

    # Assertion 26: Strict memory footprint ceiling under 250MB
    assert peak_mb < 250.0, f"Memory footprint exceeded 250MB: {peak_mb:.2f} MB"

    print("=" * 70)
    print("ALL 26 ASSERTIONS PASSED WITH ZERO MOCKS OR PHANTOM DAEMONS")
    print("=" * 70)

if __name__ == "__main__":
    main()
