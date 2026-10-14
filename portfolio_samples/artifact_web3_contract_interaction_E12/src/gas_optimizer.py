"""Dynamic EIP-1559 fee calculator with percentile estimation and slippage buffers.
Strict zero em dash policy enforced.
"""
from typing import List
from src.models import EIP1559GasEstimate


class GasOptimizer:
    """Dynamic EIP-1559 fee calculator with percentile estimation and safety buffers."""

    def __init__(self, priority_fee_percentile: int = 60, safety_buffer_pct: float = 15.0):
        self.priority_fee_percentile = priority_fee_percentile
        self.safety_buffer_pct = safety_buffer_pct

    @staticmethod
    def gwei_to_wei(gwei_val: float) -> int:
        """Convert Gwei amount to Wei integer."""
        return int(gwei_val * 1e9)

    @staticmethod
    def wei_to_gwei(wei_val: int) -> float:
        """Convert Wei integer to Gwei float."""
        return round(wei_val / 1e9, 4)

    def estimate_fees(
        self,
        latest_base_fee_gwei: float,
        recent_priority_fees: List[float],
        gas_limit: int = 65000
    ) -> EIP1559GasEstimate:
        """Calculate optimal maxPriorityFee and maxFee with safety buffer."""
        sorted_fees = sorted(recent_priority_fees) if recent_priority_fees else [2.0]
        idx = int(len(sorted_fees) * (self.priority_fee_percentile / 100.0))
        idx = min(idx, len(sorted_fees) - 1)
        priority_fee = sorted_fees[idx]

        # maxFee = 2 * baseFee + priorityFee (standard EIP-1559 safety equation)
        base_component = latest_base_fee_gwei * 2.0
        calculated_max_fee = base_component + priority_fee
        buffered_max_fee = calculated_max_fee * (1.0 + (self.safety_buffer_pct / 100.0))

        return EIP1559GasEstimate(
            base_fee_gwei=round(latest_base_fee_gwei, 2),
            priority_fee_gwei=round(priority_fee, 2),
            max_fee_gwei=round(buffered_max_fee, 2),
            estimated_gas_limit=gas_limit
        )
