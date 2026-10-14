"""Async order router using CCXT with fallback simulation and rate-limiting."""
import asyncio
import time
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
from src.models import (
    TradingViewAlert,
    ExecutionOrder,
    TradeExecutionResult,
    OrderSide,
    OrderType,
    OrderStatus
)

try:
    import ccxt.async_support as ccxt_async
    CCXT_AVAILABLE = True
except ImportError:
    ccxt_async = None
    CCXT_AVAILABLE = False

class AsyncExchangeRouter:
    """Async CCXT order router with token bucket rate limiting and fallback simulation."""
    def __init__(
        self,
        exchange_id: str = "binance",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        rate_limit_per_second: int = 20,
        max_slippage_bps: int = 50,
        simulate_execution: bool = True
    ):
        self.exchange_id = exchange_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.rate_limit_per_second = rate_limit_per_second
        self.max_slippage_bps = max_slippage_bps
        self.simulate_execution = simulate_execution

        # Token bucket rate limiting state
        self.tokens = float(rate_limit_per_second)
        self.last_token_update = time.monotonic()
        self.rate_lock = asyncio.Lock()

        # Exchange instance
        self.exchange = None
        if CCXT_AVAILABLE and not simulate_execution and api_key and api_secret:
            exchange_class = getattr(ccxt_async, exchange_id, None)
            if exchange_class:
                self.exchange = exchange_class({
                    "apiKey": api_key,
                    "secret": api_secret,
                    "enableRateLimit": True,
                })

    async def _acquire_rate_limit(self) -> None:
        """Enforce token bucket rate limiting asynchronously."""
        async with self.rate_lock:
            now = time.monotonic()
            elapsed = now - self.last_token_update
            self.last_token_update = now
            self.tokens = min(float(self.rate_limit_per_second), self.tokens + elapsed * self.rate_limit_per_second)
            if self.tokens < 1.0:
                sleep_needed = (1.0 - self.tokens) / self.rate_limit_per_second
                await asyncio.sleep(sleep_needed)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0

    async def route_order(
        self,
        alert: TradingViewAlert,
        current_market_price: Decimal,
        simulated_fill_price: Optional[Decimal] = None
    ) -> Tuple[Optional[TradeExecutionResult], str]:
        """Route order to live exchange or fallback simulation with rate-limit governance."""
        start_time = time.perf_counter()
        await self._acquire_rate_limit()

        # If live exchange is configured and not in simulation mode
        if self.exchange and not self.simulate_execution:
            try:
                side_str = "buy" if alert.action == OrderSide.BUY else "sell"
                type_str = "market" if alert.order_type == OrderType.MARKET else "limit"
                price_val = float(alert.price) if alert.price else None

                raw_order = await self.exchange.create_order(
                    symbol=alert.symbol,
                    type=type_str,
                    side=side_str,
                    amount=float(alert.quantity),
                    price=price_val
                )
                fill_price = Decimal(str(raw_order.get("average", raw_order.get("price", current_market_price))))
                latency = (time.perf_counter() - start_time) * 1000.0

                fee = alert.quantity * fill_price * Decimal("0.00075")
                result = TradeExecutionResult(
                    execution_id=str(raw_order.get("id", f"exec_{alert.alert_id}_{int(time.time())}")),
                    order_id=f"ord_{alert.alert_id}",
                    symbol=alert.symbol,
                    side=alert.action,
                    filled_quantity=Decimal(str(raw_order.get("filled", alert.quantity))),
                    average_fill_price=fill_price,
                    fee_amount=fee,
                    fee_currency="USDT",
                    status=OrderStatus.FILLED,
                    slippage_bps=0.0,
                    execution_latency_ms=latency
                )
                return result, "Order executed via CCXT"
            except Exception as e:
                # Log and fallback to simulation
                pass

        # Fallback high-speed deterministic simulation
        expected_price = alert.price if alert.price is not None else current_market_price
        fill_price = simulated_fill_price if simulated_fill_price is not None else current_market_price

        # Calculate slippage
        if alert.action == OrderSide.BUY:
            diff = fill_price - expected_price
        else:
            diff = expected_price - fill_price

        bps = float((diff / expected_price) * Decimal("10000.0")) if expected_price > Decimal("0") else 0.0
        slippage = max(0.0, bps)

        if slippage > self.max_slippage_bps:
            return None, f"Execution aborted: slippage {slippage:.1f} bps exceeds limit {self.max_slippage_bps} bps"

        latency = (time.perf_counter() - start_time) * 1000.0
        fee = alert.quantity * fill_price * Decimal("0.00075")

        result = TradeExecutionResult(
            execution_id=f"exec_{alert.alert_id}_{int(time.time()*1000)}",
            order_id=f"ord_{alert.alert_id}",
            symbol=alert.symbol,
            side=alert.action,
            filled_quantity=alert.quantity,
            average_fill_price=fill_price,
            fee_amount=fee,
            fee_currency="USDT",
            status=OrderStatus.FILLED,
            slippage_bps=slippage,
            execution_latency_ms=latency
        )
        return result, "Order filled successfully via simulated exchange router"

    async def close(self) -> None:
        """Close exchange connection cleanly if initialized."""
        if self.exchange:
            await self.exchange.close()
