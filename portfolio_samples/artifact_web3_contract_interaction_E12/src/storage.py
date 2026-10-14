"""Dual-tier storage: SQLite WAL local audit cache and PostgreSQL 18 on port 5433.
Strict zero em dash policy enforced.
"""
import sqlite3
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from src.config import Web3ClientConfig


class Web3Storage:
    """Manages SQLite WAL local caching and PostgreSQL 18 schema verification."""

    def __init__(self, config: Optional[Web3ClientConfig] = None):
        self.config = config or Web3ClientConfig()
        self.sqlite_conn: Optional[sqlite3.Connection] = None
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialize SQLite database with WAL mode."""
        self.sqlite_conn = sqlite3.connect(self.config.sqlite_db_path, timeout=5.0)
        self.sqlite_conn.execute("PRAGMA journal_mode=WAL;")
        self.sqlite_conn.execute("PRAGMA busy_timeout=5000;")
        self.sqlite_conn.execute("""
            CREATE TABLE IF NOT EXISTS transaction_audits (
                tx_hash TEXT PRIMARY KEY,
                chain TEXT NOT NULL,
                contract_address TEXT NOT NULL,
                function_name TEXT NOT NULL,
                status TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        self.sqlite_conn.commit()

    def record_tx(
        self,
        tx_hash: str,
        chain: str,
        contract_addr: str,
        func_name: str,
        status: str,
        details: Dict[str, Any]
    ) -> None:
        """Store transaction record in local SQLite database."""
        if not self.sqlite_conn:
            return
        query = """
            INSERT OR REPLACE INTO transaction_audits (
                tx_hash, chain, contract_address, function_name, status, details_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        now = datetime.now(timezone.utc).isoformat()
        self.sqlite_conn.execute(query, (
            tx_hash,
            chain,
            contract_addr,
            func_name,
            status,
            json.dumps(details),
            now
        ))
        self.sqlite_conn.commit()

    def get_transactions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent transactions from SQLite."""
        if not self.sqlite_conn:
            return []
        cursor = self.sqlite_conn.cursor()
        cursor.execute(
            """
            SELECT tx_hash, chain, contract_address, function_name, status, details_json, created_at
            FROM transaction_audits ORDER BY created_at DESC LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        return [
            {
                "tx_hash": r[0],
                "chain": r[1],
                "contract_address": r[2],
                "function_name": r[3],
                "status": r[4],
                "details": json.loads(r[5]),
                "created_at": r[6],
            }
            for r in rows
        ]

    def init_postgres_schema(self) -> bool:
        """Initialize PostgreSQL 18 schema e12_web3_evm if available."""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.config.pg_host,
                port=self.config.pg_port,
                user=self.config.pg_user,
                password=self.config.pg_password,
                dbname=self.config.pg_database,
                connect_timeout=3
            )
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.config.pg_schema};")
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.evm_tx_history (
                        tx_hash VARCHAR(66) PRIMARY KEY,
                        chain VARCHAR(32) NOT NULL,
                        contract_address VARCHAR(42) NOT NULL,
                        function_name VARCHAR(64) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        details JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
            conn.commit()
            conn.close()
            return True
        except Exception:
            # Graceful offline mode when PostgreSQL cluster is not active
            return False

    def close(self) -> None:
        """Close SQLite database connection cleanly."""
        if self.sqlite_conn:
            self.sqlite_conn.close()
            self.sqlite_conn = None
