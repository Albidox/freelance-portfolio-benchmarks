"""Dynamic PostgreSQL 18 schema loader and connection manager for e7_tradingview_bot."""
import psycopg2
from psycopg2 import sql
from typing import Optional, List, Dict, Any
from src.config import TradingBotConfig
from src.models import TradeExecutionResult

class DatabaseManager:
    def __init__(self, config: Optional[TradingBotConfig] = None):
        self.config = config or TradingBotConfig()

    def get_connection(self):
        """Establish direct psycopg2 connection to PostgreSQL 18 on port 5433."""
        return psycopg2.connect(
            host=self.config.db_host,
            port=self.config.db_port,
            user=self.config.db_user,
            password=self.config.db_password,
            dbname=self.config.db_name
        )

    def init_postgres_schema(self) -> bool:
        """Create schema and table with transaction isolation."""
        ddl = f"""
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
        CREATE INDEX IF NOT EXISTS idx_exec_symbol ON {self.config.db_schema}.trade_executions(symbol);
        CREATE INDEX IF NOT EXISTS idx_exec_time ON {self.config.db_schema}.trade_executions(executed_at DESC);
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()
        return True

    def record_execution_pg(self, exec_result: TradeExecutionResult) -> bool:
        """Persist trade execution record to PostgreSQL 18 with transaction isolation."""
        insert_sql = f"""
        INSERT INTO {self.config.db_schema}.trade_executions (
            execution_id, order_id, symbol, side, filled_quantity,
            average_fill_price, fee_amount, fee_currency, status,
            slippage_bps, executed_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (execution_id) DO UPDATE SET
            status = EXCLUDED.status,
            slippage_bps = EXCLUDED.slippage_bps;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(insert_sql, (
                    exec_result.execution_id,
                    exec_result.order_id,
                    exec_result.symbol,
                    exec_result.side.value,
                    float(exec_result.filled_quantity),
                    float(exec_result.average_fill_price),
                    float(exec_result.fee_amount),
                    exec_result.fee_currency,
                    exec_result.status.value,
                    float(exec_result.slippage_bps),
                    exec_result.executed_at
                ))
            conn.commit()
        return True

    def batch_record_executions_pg(self, exec_results: List[TradeExecutionResult]) -> int:
        """Batch persist trade executions in a single atomic transaction."""
        if not exec_results:
            return 0
        insert_sql = f"""
        INSERT INTO {self.config.db_schema}.trade_executions (
            execution_id, order_id, symbol, side, filled_quantity,
            average_fill_price, fee_amount, fee_currency, status,
            slippage_bps, executed_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (execution_id) DO NOTHING;
        """
        records = [
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
                float(r.slippage_bps),
                r.executed_at
            )
            for r in exec_results
        ]
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(insert_sql, records)
            conn.commit()
        return len(records)
