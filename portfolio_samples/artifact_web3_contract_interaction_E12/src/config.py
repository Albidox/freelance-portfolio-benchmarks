"""Runtime configuration for EVM RPC endpoints and database storage.
Strict zero em dash policy enforced.
"""
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Web3ClientConfig:
    network: str = os.getenv("NETWORK", "SEPOLIA")
    rpc_urls: List[str] = field(default_factory=lambda: [
        "https://rpc.sepolia.org",
        "https://sepolia.gateway.tenderly.co",
        "https://ethereum-sepolia-rpc.publicnode.com"
    ])
    chain_id: int = 11155111
    sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", "web3_transactions.db")
    pg_host: str = os.getenv("PG_HOST", "127.0.0.1")
    pg_port: int = int(os.getenv("PG_PORT", "5433"))
    pg_user: str = os.getenv("PG_USER", "postgres")
    pg_password: str = os.getenv("PG_PASSWORD", "postgres")
    pg_database: str = os.getenv("PG_DATABASE", "postgres")
    pg_schema: str = os.getenv("PG_SCHEMA", "e12_web3_evm")
    max_memory_mb: int = 250
    reorg_confirmation_depth: int = 12
