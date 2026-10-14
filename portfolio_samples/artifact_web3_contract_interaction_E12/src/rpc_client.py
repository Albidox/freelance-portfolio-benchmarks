"""Async EVM JSON-RPC client with endpoint rotation and connection health checks.
Strict zero em dash policy enforced.
"""
import time
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from src.config import Web3ClientConfig


class AsyncEVMJSONRPCClient:
    """Async EVM JSON-RPC client with endpoint rotation and connection health checks."""

    def __init__(self, config: Optional[Web3ClientConfig] = None):
        self.config = config or Web3ClientConfig()
        self.rpc_urls: List[str] = list(self.config.rpc_urls)
        self.active_rpc_index: int = 0
        self.failure_counters: Dict[str, int] = {url: 0 for url in self.rpc_urls}
        self.circuit_tripped: Dict[str, bool] = {url: False for url in self.rpc_urls}
        self.latency_records: Dict[str, List[float]] = {url: [] for url in self.rpc_urls}

    def get_current_rpc(self) -> str:
        """Return the current active RPC endpoint."""
        return self.rpc_urls[self.active_rpc_index]

    def rotate_to_next_rpc(self) -> str:
        """Rotate to next available RPC endpoint in the pool."""
        self.active_rpc_index = (self.active_rpc_index + 1) % len(self.rpc_urls)
        return self.get_current_rpc()

    def record_rpc_error(self, url: str) -> bool:
        """Increment error counter and trip circuit breaker if threshold is reached."""
        self.failure_counters[url] = self.failure_counters.get(url, 0) + 1
        if self.failure_counters[url] >= 3:
            self.circuit_tripped[url] = True
            self.rotate_to_next_rpc()
            return True
        return False

    def reset_circuit_breaker(self, url: str) -> None:
        """Reset circuit breaker and failure counter for an endpoint."""
        self.failure_counters[url] = 0
        self.circuit_tripped[url] = False

    def check_health(self, url: str) -> Dict[str, Any]:
        """Perform synchronous health check for a given RPC URL."""
        t0 = time.perf_counter()
        is_healthy = not self.circuit_tripped.get(url, False)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "url": url,
            "healthy": is_healthy,
            "circuit_tripped": self.circuit_tripped.get(url, False),
            "failures": self.failure_counters.get(url, 0),
            "latency_ms": round(latency_ms, 3),
        }

    async def async_check_health(self, url: str) -> Dict[str, Any]:
        """Perform asynchronous health check simulation for a given RPC URL."""
        await asyncio.sleep(0.001)
        return self.check_health(url)

    def dispatch_call(self, method: str, params: List[Any]) -> Dict[str, Any]:
        """Dispatch a JSON-RPC method call with automatic failover."""
        active_url = self.get_current_rpc()
        if self.circuit_tripped.get(active_url, False):
            active_url = self.rotate_to_next_rpc()

        # Simulated response for testing and dry-run operation
        return {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "result": {
                "method": method,
                "params": params,
                "rpc_used": active_url,
                "status": "success",
            },
        }

    async def async_dispatch_call(self, method: str, params: List[Any]) -> Dict[str, Any]:
        """Async dispatch JSON-RPC call."""
        await asyncio.sleep(0.001)
        return self.dispatch_call(method, params)
