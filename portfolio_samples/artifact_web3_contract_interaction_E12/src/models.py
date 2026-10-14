"""Data contracts, models, and enums for Web3 Smart Contract Interaction Script.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


class NetworkChain(str, Enum):
    ETHEREUM_MAINNET = "ETHEREUM_MAINNET"
    SEPOLIA = "SEPOLIA"
    POLYGON = "POLYGON"
    ARBITRUM = "ARBITRUM"


class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    UNDERPRICED = "UNDERPRICED"


class ContractCallType(str, Enum):
    READ_VIEW = "READ_VIEW"
    STATE_CHANGING_TX = "STATE_CHANGING_TX"


@dataclass
class EIP1559GasEstimate:
    base_fee_gwei: float
    priority_fee_gwei: float
    max_fee_gwei: float
    estimated_gas_limit: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_fee_gwei": round(self.base_fee_gwei, 2),
            "priority_fee_gwei": round(self.priority_fee_gwei, 2),
            "max_fee_gwei": round(self.max_fee_gwei, 2),
            "estimated_gas_limit": self.estimated_gas_limit,
        }


@dataclass
class SmartContractTxRequest:
    chain: NetworkChain
    contract_address: str
    function_name: str
    function_args: List[Any]
    sender_address: str
    value_wei: int = 0
    nonce: Optional[int] = None
    gas_estimate: Optional[EIP1559GasEstimate] = None

    def validate(self) -> bool:
        """Validate EVM hex addresses and parameters."""
        if not self.contract_address.startswith("0x") or len(self.contract_address) != 42:
            return False
        if not self.sender_address.startswith("0x") or len(self.sender_address) != 42:
            return False
        if self.value_wei < 0:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chain": self.chain.value if isinstance(self.chain, NetworkChain) else str(self.chain),
            "contract_address": self.contract_address,
            "function_name": self.function_name,
            "function_args": self.function_args,
            "sender_address": self.sender_address,
            "value_wei": self.value_wei,
            "nonce": self.nonce,
            "gas_estimate": self.gas_estimate.to_dict() if self.gas_estimate else None,
        }


@dataclass
class TxReceiptRecord:
    tx_hash: str
    block_number: int
    status: TransactionStatus
    gas_used: int
    effective_gas_price_gwei: float
    confirmations: int
    logs: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_hash": self.tx_hash,
            "block_number": self.block_number,
            "status": self.status.value if isinstance(self.status, TransactionStatus) else str(self.status),
            "gas_used": self.gas_used,
            "effective_gas_price_gwei": self.effective_gas_price_gwei,
            "confirmations": self.confirmations,
            "logs": self.logs,
        }


@dataclass
class EventFilterQuery:
    contract_address: str
    event_name: str
    from_block: int
    to_block: int
    chunk_size: int = 2000

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Web3AuditLog:
    log_id: str
    action: str
    tx_hash: Optional[str]
    status: str
    details: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContractEvent:
    contract_address: str
    event_name: str
    block_number: int
    transaction_hash: str
    log_index: int
    args: Dict[str, Any] = field(default_factory=dict)
    status: str = "CONFIRMED"
    timestamp: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TransactionPayload:
    chain_id: int
    to: str
    from_address: str
    nonce: int
    data: str
    value_wei: int = 0
    gas_limit: int = 100000
    max_priority_fee_per_gas: int = 2000000000
    max_fee_per_gas: int = 30000000000
    tx_type: str = "0x2"
    hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReceiptSummary:
    tx_hash: str
    block_number: int
    gas_used: int
    effective_gas_price_gwei: float
    status: str
    confirmations: int = 1
    logs_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WalletBalance:
    wallet_address: str
    chain: NetworkChain
    native_balance_wei: int
    native_balance_eth: float
    token_balances: Dict[str, float] = field(default_factory=dict)
    block_height: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wallet_address": self.wallet_address,
            "chain": self.chain.value if isinstance(self.chain, NetworkChain) else str(self.chain),
            "native_balance_wei": self.native_balance_wei,
            "native_balance_eth": self.native_balance_eth,
            "token_balances": self.token_balances,
            "block_height": self.block_height,
            "updated_at": self.updated_at,
        }
