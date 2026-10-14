"""Web3 client wrapper managing multi-RPC failover, ABI loading, and circuit breaker trip detection.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional
import json
import time
from src.config import Web3ClientConfig


class EVMContractClient:
    """EVM Contract Client with multi-RPC failover and ABI management."""

    def __init__(self, config: Optional[Web3ClientConfig] = None):
        self.config = config or Web3ClientConfig()
        self.rpc_urls = list(self.config.rpc_urls)
        self.active_rpc_index = 0
        self.failure_counters: Dict[str, int] = {url: 0 for url in self.rpc_urls}
        self.circuit_tripped: Dict[str, bool] = {url: False for url in self.rpc_urls}
        self.loaded_abis: Dict[str, List[Dict[str, Any]]] = {}

    def get_current_rpc(self) -> str:
        """Return the current active RPC endpoint."""
        return self.rpc_urls[self.active_rpc_index]

    def rotate_to_next_rpc(self) -> str:
        """Rotate to next available RPC endpoint in pool."""
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

    def load_abi(self, contract_name: str, abi_json_str: str) -> List[Dict[str, Any]]:
        """Parse, validate, and register contract ABI specification."""
        try:
            abi = json.loads(abi_json_str)
            if not isinstance(abi, list):
                raise ValueError("ABI must be a JSON array of function/event objects")
            self.loaded_abis[contract_name] = abi
            return abi
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed ABI JSON: {str(e)}")

    def get_function_signature(self, contract_name: str, function_name: str) -> Optional[Dict[str, Any]]:
        """Find function signature dictionary in loaded contract ABI."""
        abi = self.loaded_abis.get(contract_name)
        if not abi:
            return None
        for item in abi:
            if item.get("type") == "function" and item.get("name") == function_name:
                return item
        return None

    def simulate_call(self, contract_address: str, function_name: str, args: List[Any]) -> Dict[str, Any]:
        """Execute simulated read-only call returning structured result."""
        active_url = self.get_current_rpc()
        if self.circuit_tripped.get(active_url, False):
            active_url = self.rotate_to_next_rpc()

        return {
            "success": True,
            "contract": contract_address,
            "function": function_name,
            "rpc_used": active_url,
            "return_value": 42,
            "timestamp": int(time.time()),
        }
