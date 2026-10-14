"""Storage persistence engine supporting Native PostgreSQL 18 and SQLite WAL caching."""
import sqlite3
import json
from typing import Dict, Any, Optional
from src.config import TradingBotConfig
from src.models import TradeExecutionResult

class TradingBotStorage:
    def __init__(self, config: TradingBotConfig):
        self.config = config

    def init_sqlite_cache(self) -> None:
        """Initialize local SQLite WAL database for high-speed offline trade audit."""
        with sqlite3.connect(self.config.sqlite_cache_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_executions (
                    execution_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    filled_quantity REAL NOT NULL,
                    average_fill_price REAL NOT NULL,
                    fee_amount REAL NOT NULL,
                    fee_currency TEXT NOT NULL,
                    status TEXT NOT NULL,
                    slippage_bps REAL NOT NULL,
                    executed_at TEXT NOT NULL
                );
            """)
            conn.commit()

    def record_execution_sqlite(self, exec_result: TradeExecutionResult) -> bool:
        """Persist execution record into local SQLite WAL store."""
        with sqlite3.connect(self.config.sqlite_cache_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO trade_executions (
                    execution_id, order_id, symbol, side, filled_quantity,
                    average_fill_price, fee_amount, fee_currency, status,
                    slippage_bps, executed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                exec_result.execution_id,
                exec_result.order_id,
                exec_result.symbol,
                exec_result.side.value,
                float(exec_result.filled_quantity),
                float(exec_result.average_fill_price),
                float(exec_result.fee_amount),
                exec_result.fee_currency,
                exec_result.status.value,
                exec_result.slippage_bps,
                exec_result.executed_at
            ))
            conn.commit()
        return True

    def batch_record_sqlite(self, exec_results: list) -> int:
        """Batch persist execution records into local SQLite WAL store."""
        with sqlite3.connect(self.config.sqlite_cache_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.executemany("""
                INSERT OR REPLACE INTO trade_executions (
                    execution_id, order_id, symbol, side, filled_quantity,
                    average_fill_price, fee_amount, fee_currency, status,
                    slippage_bps, executed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, [
                (
                    r.execution_id,
                    r.order_id,
                    r.symbol,
                    r.side.value,
                    float(r.filled_quantity),
                    float(r.average_fill_price),
                    float(r.fee_amount),
                    r.fee_currency,
                    r.status.value,
                    r.slippage_bps,
                    r.executed_at
                )
                for r in exec_results
            ])
            conn.commit()
        return len(exec_results)

    def get_postgres_schema_ddl(self) -> str:
        """Return idempotent PostgreSQL 18 DDL for dedicated schema isolation."""
        return f"""
        CREATE SCHEMA IF NOT EXISTS {self.config.db_schema};
        CREATE TABLE IF NOT EXISTS {self.config.db_schema}.trade_executions (
            execution_id VARCHAR(64) PRIMARY KEY,
            order_id VARCHAR(64) NOT NULL,
            symbol VARCHAR(32) NOT NULL,
            side VARCHAR(16) NOT NULL,
            filled_quantity NUMERIC(18, 8) NOT NULL,
            average_fill_price NUMERIC(18, 8) NOT NULL,
            fee_amount NUMERIC(18, 8) NOT NULL,
            fee_currency VARCHAR(16) NOT NULL,
            status VARCHAR(32) NOT NULL,
            slippage_bps NUMERIC(10, 4) NOT NULL,
            executed_at TIMESTAMPTZ NOT NULL
        );
        """
