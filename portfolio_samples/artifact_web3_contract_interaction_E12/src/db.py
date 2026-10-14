"""Dynamic PostgreSQL 18 schema loader and transaction audit logger.
Dynamic schema isolation e12_web3_evm on port 5433.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional
import json
from src.config import Web3ClientConfig
from src.models import ContractEvent


class DatabaseManager:
    """Manages PostgreSQL 18 schema initialization and batch EVM transaction persistence."""

    def __init__(self, config: Optional[Web3ClientConfig] = None):
        self.config = config or Web3ClientConfig()
        self.conn = None
        self._connected = False

    def get_connection(self):
        """Establish or return active PostgreSQL connection."""
        if self.conn is not None and not self.conn.closed:
            return self.conn
        try:
            import psycopg2
            self.conn = psycopg2.connect(
                host=self.config.pg_host,
                port=self.config.pg_port,
                user=self.config.pg_user,
                password=self.config.pg_password,
                dbname=self.config.pg_database,
                connect_timeout=3,
            )
            self._connected = True
            return self.conn
        except Exception:
            self._connected = False
            return None

    def init_schema(self) -> bool:
        """Create schema e12_web3_evm and required tables if not existing."""
        conn = self.get_connection()
        if not conn:
            return False
        try:
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
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.contract_events (
                        event_id VARCHAR(64) PRIMARY KEY,
                        contract_address VARCHAR(42) NOT NULL,
                        event_name VARCHAR(64) NOT NULL,
                        block_number BIGINT NOT NULL,
                        tx_hash VARCHAR(66) NOT NULL,
                        log_index INT NOT NULL,
                        args JSONB NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.config.pg_schema}.execution_audits (
                        log_id VARCHAR(64) PRIMARY KEY,
                        action VARCHAR(64) NOT NULL,
                        tx_hash VARCHAR(66),
                        status VARCHAR(32) NOT NULL,
                        duration_ms NUMERIC(10, 2) NOT NULL,
                        details JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
            conn.commit()
            return True
        except Exception:
            if conn:
                conn.rollback()
            return False

    def insert_tx(
        self,
        tx_hash: str,
        chain: str,
        contract_address: str,
        function_name: str,
        status: str,
        details: Dict[str, Any]
    ) -> bool:
        """Persist a single EVM transaction record."""
        conn = self.get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.config.pg_schema}.evm_tx_history
                    (tx_hash, chain, contract_address, function_name, status, details)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tx_hash) DO UPDATE SET
                        status = EXCLUDED.status,
                        details = EXCLUDED.details;
                    """,
                    (tx_hash, chain, contract_address, function_name, status, json.dumps(details))
                )
            conn.commit()
            return True
        except Exception:
            if conn:
                conn.rollback()
            return False

    def batch_insert_txs(self, records: List[Dict[str, Any]]) -> int:
        """Batch insert EVM transaction records using execute_values."""
        conn = self.get_connection()
        if not conn or not records:
            return 0
        try:
            from psycopg2.extras import execute_values
            rows = [
                (
                    r["tx_hash"],
                    r["chain"],
                    r["contract_address"],
                    r["function_name"],
                    r["status"],
                    json.dumps(r.get("details", {}))
                )
                for r in records
            ]
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    f"""
                    INSERT INTO {self.config.pg_schema}.evm_tx_history
                    (tx_hash, chain, contract_address, function_name, status, details)
                    VALUES %s
                    ON CONFLICT (tx_hash) DO UPDATE SET
                        status = EXCLUDED.status,
                        details = EXCLUDED.details;
                    """,
                    rows
                )
            conn.commit()
            return len(records)
        except Exception:
            if conn:
                conn.rollback()
            return 0

    def insert_event(self, event: ContractEvent) -> bool:
        """Persist smart contract event log."""
        conn = self.get_connection()
        if not conn:
            return False
        try:
            event_id = f"{event.transaction_hash}_{event.log_index}"
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.config.pg_schema}.contract_events
                    (event_id, contract_address, event_name, block_number, tx_hash, log_index, args, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id) DO UPDATE SET
                        status = EXCLUDED.status;
                    """,
                    (
                        event_id,
                        event.contract_address,
                        event.event_name,
                        event.block_number,
                        event.transaction_hash,
                        event.log_index,
                        json.dumps(event.args),
                        event.status
                    )
                )
            conn.commit()
            return True
        except Exception:
            if conn:
                conn.rollback()
            return False

    def insert_audit(
        self,
        log_id: str,
        action: str,
        tx_hash: Optional[str],
        status: str,
        duration_ms: float,
        details: Dict[str, Any]
    ) -> bool:
        """Persist execution audit log."""
        conn = self.get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.config.pg_schema}.execution_audits
                    (log_id, action, tx_hash, status, duration_ms, details)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (log_id) DO NOTHING;
                    """,
                    (log_id, action, tx_hash, status, duration_ms, json.dumps(details))
                )
            conn.commit()
            return True
        except Exception:
            if conn:
                conn.rollback()
            return False

    def get_tx_count(self) -> int:
        """Return total count of recorded transactions in PostgreSQL."""
        conn = self.get_connection()
        if not conn:
            return 0
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self.config.pg_schema}.evm_tx_history;")
                row = cur.fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    def close(self):
        """Close database connection cleanly."""
        if self.conn and not self.conn.closed:
            self.conn.close()
            self.conn = None
            self._connected = False
