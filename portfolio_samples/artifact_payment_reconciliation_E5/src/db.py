"""PostgreSQL 18 transactional ledger persistence with dynamic schema isolation.
Zero em dashes policy strictly enforced.
"""
import psycopg2
from typing import List, Dict, Any, Optional
from decimal import Decimal
from src.config import PaymentReconcilerConfig
from src.models import PaymentEvent, PaymentStatus, OrderRecord


class LedgerStorageEngine:
    """Manages transactional persistence of events, orders, and payment ledger in PostgreSQL 18."""

    def __init__(self, config: PaymentReconcilerConfig, schema_override: Optional[str] = None):
        self.config = config
        self.schema = schema_override or config.db_schema

    def get_connection(self):
        """Connect to Native PostgreSQL 18 on port 5433 with configured schema search path."""
        return psycopg2.connect(
            host=self.config.db_host,
            port=self.config.db_port,
            user=self.config.db_user,
            password=self.config.db_password,
            dbname=self.config.db_name,
            options=f"-c search_path={self.schema},public",
        )

    def initialize_schema(self) -> None:
        """Create dynamic schema and transactional tables with strict idempotency."""
        ddl = f"""
        CREATE SCHEMA IF NOT EXISTS {self.schema};
        SET search_path TO {self.schema};

        CREATE TABLE IF NOT EXISTS webhook_events (
            id SERIAL PRIMARY KEY,
            gateway VARCHAR(32) NOT NULL,
            event_id VARCHAR(128) NOT NULL,
            event_type VARCHAR(128) NOT NULL,
            received_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_gateway_event UNIQUE (gateway, event_id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id VARCHAR(128) PRIMARY KEY,
            customer_id VARCHAR(128) NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            currency VARCHAR(8) NOT NULL,
            status VARCHAR(32) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS payment_ledger (
            payment_id VARCHAR(128) PRIMARY KEY,
            gateway VARCHAR(32) NOT NULL,
            order_id VARCHAR(128),
            amount NUMERIC(12, 2) NOT NULL,
            currency VARCHAR(8) NOT NULL,
            status VARCHAR(32) NOT NULL,
            fee NUMERIC(12, 2) DEFAULT 0.00,
            tax NUMERIC(12, 2) DEFAULT 0.00,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS reconciliation_audits (
            id SERIAL PRIMARY KEY,
            payment_id VARCHAR(128),
            audit_note TEXT NOT NULL,
            is_resolved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_ledger_status ON payment_ledger(status);
        CREATE INDEX IF NOT EXISTS idx_events_lookup ON webhook_events(gateway, event_id);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        CREATE INDEX IF NOT EXISTS idx_audits_payment ON reconciliation_audits(payment_id);
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()

    def record_event_and_update_ledger(self, event: PaymentEvent) -> bool:
        """Atomically record webhook event and update payment ledger."""
        sql_event = f"""
        INSERT INTO {self.schema}.webhook_events (gateway, event_id, event_type)
        VALUES (%s, %s, %s)
        ON CONFLICT (gateway, event_id) DO NOTHING;
        """
        sql_ledger = f"""
        INSERT INTO {self.schema}.payment_ledger
        (payment_id, gateway, order_id, amount, currency, status, fee, tax, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (payment_id) DO UPDATE SET
            status = EXCLUDED.status,
            amount = EXCLUDED.amount,
            updated_at = CURRENT_TIMESTAMP;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql_event,
                    (event.gateway.value, event.event_id, f"payment.{event.status.value.lower()}"),
                )
                cur.execute(
                    sql_ledger,
                    (
                        event.payment_id,
                        event.gateway.value,
                        event.order_id,
                        float(event.amount),
                        event.currency,
                        event.status.value,
                        float(event.fee),
                        float(event.tax),
                    ),
                )
            conn.commit()
        return True

    def batch_record_events(self, events: List[PaymentEvent]) -> int:
        """Batch record webhook events and update ledger in single transaction."""
        if not events:
            return 0

        sql_event = f"""
        INSERT INTO {self.schema}.webhook_events (gateway, event_id, event_type)
        VALUES (%s, %s, %s)
        ON CONFLICT (gateway, event_id) DO NOTHING;
        """
        sql_ledger = f"""
        INSERT INTO {self.schema}.payment_ledger
        (payment_id, gateway, order_id, amount, currency, status, fee, tax, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (payment_id) DO UPDATE SET
            status = EXCLUDED.status,
            amount = EXCLUDED.amount,
            updated_at = CURRENT_TIMESTAMP;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                for event in events:
                    cur.execute(
                        sql_event,
                        (event.gateway.value, event.event_id, f"payment.{event.status.value.lower()}"),
                    )
                    cur.execute(
                        sql_ledger,
                        (
                            event.payment_id,
                            event.gateway.value,
                            event.order_id,
                            float(event.amount),
                            event.currency,
                            event.status.value,
                            float(event.fee),
                            float(event.tax),
                        ),
                    )
            conn.commit()
        return len(events)

    def upsert_order(self, order: OrderRecord) -> bool:
        """Upsert order record into orders table."""
        sql = f"""
        INSERT INTO {self.schema}.orders
        (order_id, customer_id, amount, currency, status, updated_at)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (order_id) DO UPDATE SET
            status = EXCLUDED.status,
            amount = EXCLUDED.amount,
            updated_at = CURRENT_TIMESTAMP;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        order.order_id,
                        order.customer_id,
                        float(order.amount),
                        order.currency,
                        order.status,
                    ),
                )
            conn.commit()
        return True

    def batch_upsert_orders(self, orders: List[OrderRecord]) -> int:
        """Batch upsert order records in single transaction."""
        if not orders:
            return 0
        sql = f"""
        INSERT INTO {self.schema}.orders
        (order_id, customer_id, amount, currency, status, updated_at)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (order_id) DO UPDATE SET
            status = EXCLUDED.status,
            amount = EXCLUDED.amount,
            updated_at = CURRENT_TIMESTAMP;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                for order in orders:
                    cur.execute(
                        sql,
                        (
                            order.order_id,
                            order.customer_id,
                            float(order.amount),
                            order.currency,
                            order.status,
                        ),
                    )
            conn.commit()
        return len(orders)

    def fetch_ledger_records(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch all ledger records matching optional status."""
        query = f"SELECT payment_id, gateway, order_id, amount, currency, status, fee, tax, updated_at FROM {self.schema}.payment_ledger"
        params: tuple = ()
        if status:
            query += " WHERE status = %s"
            params = (status,)
        query += " ORDER BY payment_id"

        results = []
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                for row in cur.fetchall():
                    results.append(
                        {
                            "payment_id": row[0],
                            "gateway": row[1],
                            "order_id": row[2],
                            "amount": Decimal(str(row[3])),
                            "currency": row[4],
                            "status": row[5],
                            "fee": Decimal(str(row[6])),
                            "tax": Decimal(str(row[7])),
                            "updated_at": row[8],
                        }
                    )
        return results

    def fetch_orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch orders matching optional status."""
        query = f"SELECT order_id, customer_id, amount, currency, status, updated_at FROM {self.schema}.orders"
        params: tuple = ()
        if status:
            query += " WHERE status = %s"
            params = (status,)
        query += " ORDER BY order_id"

        results = []
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                for row in cur.fetchall():
                    results.append(
                        {
                            "order_id": row[0],
                            "customer_id": row[1],
                            "amount": Decimal(str(row[2])),
                            "currency": row[3],
                            "status": row[4],
                            "updated_at": row[5],
                        }
                    )
        return results

    def record_audit(self, payment_id: str, note: str, resolved: bool = False) -> int:
        """Record an audit trail note for a reconciled discrepancy."""
        sql = f"""
        INSERT INTO {self.schema}.reconciliation_audits (payment_id, audit_note, is_resolved)
        VALUES (%s, %s, %s)
        RETURNING id;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (payment_id, note, resolved))
                row = cur.fetchone()
                audit_id = row[0] if row else 0
            conn.commit()
        return audit_id

    def clean_schema(self) -> None:
        """Drop tables in schema for fresh benchmark runs."""
        ddl = f"""
        DROP TABLE IF EXISTS {self.schema}.reconciliation_audits CASCADE;
        DROP TABLE IF EXISTS {self.schema}.payment_ledger CASCADE;
        DROP TABLE IF EXISTS {self.schema}.orders CASCADE;
        DROP TABLE IF EXISTS {self.schema}.webhook_events CASCADE;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()


# Dynamic schema loader alias
DatabaseLoader = LedgerStorageEngine
