"""Transaction manager handling nonce tracking, EIP-1559 payload formatting, and fee replacement.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, Optional, Tuple
import hashlib
import json
from src.models import SmartContractTxRequest, TransactionStatus, EIP1559GasEstimate


class TransactionManager:
    """Manages sequential nonce allocation, EIP-1559 payload creation, and replacement fees."""

    def __init__(self, sender_address: str):
        self.sender_address = sender_address.lower()
        self.current_nonce = 0
        self.submitted_txs: Dict[int, Dict[str, Any]] = {}

    def get_next_nonce(self) -> int:
        """Obtain and lock next sequential transaction nonce."""
        nonce = self.current_nonce
        self.current_nonce += 1
        return nonce

    def build_eip1559_transaction(self, request: SmartContractTxRequest, chain_id: int = 11155111) -> Dict[str, Any]:
        """Construct raw EIP-1559 Type 2 transaction dictionary."""
        if request.nonce is None:
            request.nonce = self.get_next_nonce()

        gas = request.gas_estimate or EIP1559GasEstimate(
            base_fee_gwei=20.0,
            priority_fee_gwei=2.0,
            max_fee_gwei=30.0,
            estimated_gas_limit=100000
        )

        max_priority_fee_wei = int(gas.priority_fee_gwei * 1e9)
        max_fee_wei = int(gas.max_fee_gwei * 1e9)

        tx_payload = {
            "type": "0x2",
            "chainId": chain_id,
            "nonce": request.nonce,
            "maxPriorityFeePerGas": max_priority_fee_wei,
            "maxFeePerGas": max_fee_wei,
            "gas": gas.estimated_gas_limit,
            "to": request.contract_address,
            "value": request.value_wei,
            "data": f"0x_encoded_{request.function_name}",
            "from": request.sender_address,
        }

        # Compute deterministic transaction hash simulation
        raw_repr = json.dumps(tx_payload, sort_keys=True).encode("utf-8")
        simulated_hash = "0x" + hashlib.sha256(raw_repr).hexdigest()
        tx_payload["hash"] = simulated_hash
        self.submitted_txs[request.nonce] = tx_payload
        return tx_payload

    def calculate_replacement_fee(self, original_tx: Dict[str, Any], bump_percentage: float = 15.0) -> Tuple[int, int]:
        """Calculate bumped maxFee and maxPriorityFee for replacing stuck transaction (min 10-15%)."""
        multiplier = 1.0 + (bump_percentage / 100.0)
        new_priority_fee = int(original_tx["maxPriorityFeePerGas"] * multiplier)
        new_max_fee = int(original_tx["maxFeePerGas"] * multiplier)
        return new_priority_fee, new_max_fee
