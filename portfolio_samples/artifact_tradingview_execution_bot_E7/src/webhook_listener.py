"""FastAPI webhook listener parsing PineScript alerts with HMAC authentication."""
import json
from typing import Dict, Any, Optional
from decimal import Decimal
from fastapi import FastAPI, Request, HTTPException, Header, Depends, status
from fastapi.responses import JSONResponse

from src.config import TradingBotConfig
from src.models import TradingViewAlert, OrderSide, OrderType, TradeExecutionResult
from src.webhook_receiver import WebhookReceiver
from src.signal_validator import SignalValidator
from src.exchange_executor import ExchangeExecutor
from src.risk_manager import RiskManager
from src.storage import TradingBotStorage

app = FastAPI(title="TradingView Execution Bot Webhook Listener", version="1.0.0")

config = TradingBotConfig()
receiver = WebhookReceiver(config)
validator = SignalValidator()
executor = ExchangeExecutor(max_slippage_bps=config.max_slippage_bps)
storage = TradingBotStorage(config)

@app.on_event("startup")
def startup_event():
    storage.init_sqlite_cache()

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "TradingView Execution Bot Webhook Listener",
        "replays_detected": receiver.replays_detected,
        "unauthorized_ips_blocked": receiver.unauthorized_ips_blocked,
        "tampered_payloads_blocked": receiver.tampered_payloads_blocked
    }

@app.post("/webhook/tradingview")
async def handle_tradingview_alert(
    request: Request,
    x_tradingview_signature: Optional[str] = Header(None, alias="X-TradingView-Signature"),
    x_forwarded_for: Optional[str] = Header(None, alias="X-Forwarded-For")
):
    client_ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else request.client.host
    if not receiver.verify_ip(client_ip):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"IP {client_ip} not authorized")

    raw_body = (await request.body()).decode("utf-8")

    if x_tradingview_signature:
        if not receiver.verify_hmac_signature(raw_body, x_tradingview_signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC signature")

    alert, parse_err = receiver.parse_alert_json(raw_body)
    if not alert:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=parse_err)

    if not x_tradingview_signature and alert.passphrase:
        if not receiver.verify_passphrase(alert.passphrase):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid passphrase")

    is_fresh, fresh_msg = receiver.check_timestamp_freshness(alert.timestamp)
    if not is_fresh:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=fresh_msg)

    valid_risk, risk_err = validator.validate_risk_boundaries(alert)
    if not valid_risk:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=risk_err)

    normalized_alert = validator.normalize_alert(alert)

    current_price = normalized_alert.price or Decimal("100.00")
    exec_result, exec_msg = executor.execute_order(normalized_alert, current_market_price=current_price)

    if not exec_result:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"success": False, "message": exec_msg}
        )

    storage.record_execution_sqlite(exec_result)

    return {
        "success": True,
        "message": "Order executed successfully",
        "execution": {
            "execution_id": exec_result.execution_id,
            "order_id": exec_result.order_id,
            "symbol": exec_result.symbol,
            "side": exec_result.side.value,
            "filled_quantity": float(exec_result.filled_quantity),
            "average_fill_price": float(exec_result.average_fill_price),
            "fee_amount": float(exec_result.fee_amount),
            "slippage_bps": exec_result.slippage_bps,
            "executed_at": exec_result.executed_at
        }
    }
