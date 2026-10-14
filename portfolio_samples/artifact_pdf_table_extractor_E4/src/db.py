"""Database persistence layer for Native PostgreSQL 18 with dynamic schema isolation and deduplication.
Strict zero em dash policy enforced.
"""
from typing import List, Dict, Any, Optional
from decimal import Decimal
import psycopg2
from psycopg2.extras import execute_values
from src.config import ExtractorConfig
from src.models import ExtractedInvoice


class DatabaseLoader:
    """Manages transactional insertion of invoices and line items into PostgreSQL 18."""

    def __init__(self, config: Optional[ExtractorConfig] = None):
        self.config = config or ExtractorConfig()

    def get_connection(self):
        """Open connection to local Native PostgreSQL 18 on port 5433."""
        return psycopg2.connect(
            host=self.config.db_host,
            port=self.config.db_port,
            user=self.config.db_user,
            password=self.config.db_password,
            dbname=self.config.db_name,
            options=f"-c search_path={self.config.db_schema},public",
        )

    def initialize_schema(self) -> bool:
        """Create schema and tables if they do not exist."""
        ddl = f"""
        CREATE SCHEMA IF NOT EXISTS {self.config.db_schema};
        SET search_path TO {self.config.db_schema};

        CREATE TABLE IF NOT EXISTS invoices (
            invoice_number VARCHAR(128) PRIMARY KEY,
            invoice_date DATE,
            vendor_name VARCHAR(256),
            currency VARCHAR(8),
            subtotal NUMERIC(12, 2),
            tax_amount NUMERIC(12, 2),
            total_due NUMERIC(12, 2),
            confidence_score NUMERIC(5, 4),
            is_mathematically_valid BOOLEAN,
            extracted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS invoice_line_items (
            id SERIAL PRIMARY KEY,
            invoice_number VARCHAR(128) REFERENCES invoices(invoice_number) ON DELETE CASCADE,
            line_number INT,
            item_description TEXT,
            sku_code VARCHAR(64),
            quantity NUMERIC(10, 4),
            unit_price NUMERIC(12, 4),
            total_amount NUMERIC(12, 2)
        );

        CREATE INDEX IF NOT EXISTS idx_invoices_vendor ON invoices(vendor_name);
        CREATE INDEX IF NOT EXISTS idx_line_items_inv ON invoice_line_items(invoice_number);
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(ddl)
                conn.commit()
            return True
        except Exception as e:
            print(f"Schema initialization warning: {e}")
            return False

    def persist_invoice(self, invoice: ExtractedInvoice) -> bool:
        """Transactionally persist invoice and all line items with deduplication."""
        sql_invoice = f"""
        INSERT INTO {self.config.db_schema}.invoices
        (invoice_number, invoice_date, vendor_name, currency, subtotal, tax_amount, total_due, confidence_score, is_mathematically_valid)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (invoice_number) DO UPDATE SET
            total_due = EXCLUDED.total_due,
            confidence_score = EXCLUDED.confidence_score,
            is_mathematically_valid = EXCLUDED.is_mathematically_valid;
        """
        sql_delete_items = f"""
        DELETE FROM {self.config.db_schema}.invoice_line_items
        WHERE invoice_number = %s;
        """
        sql_items = f"""
        INSERT INTO {self.config.db_schema}.invoice_line_items
        (invoice_number, line_number, item_description, sku_code, quantity, unit_price, total_amount)
        VALUES %s;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_invoice, (
                    invoice.invoice_number,
                    invoice.invoice_date,
                    invoice.vendor_name,
                    invoice.currency,
                    float(invoice.subtotal),
                    float(invoice.tax_amount),
                    float(invoice.total_due),
                    float(invoice.confidence_score),
                    invoice.is_mathematically_valid,
                ))
                # Deduplicate existing line items for this invoice
                cur.execute(sql_delete_items, (invoice.invoice_number,))

                if invoice.line_items:
                    item_rows = [
                        (
                            invoice.invoice_number,
                            item.line_number,
                            item.item_description,
                            item.sku_code,
                            float(item.quantity),
                            float(item.unit_price),
                            float(item.total_amount),
                        )
                        for item in invoice.line_items
                    ]
                    execute_values(cur, sql_items, item_rows)
            conn.commit()
        return True


# Compatibility alias
PostgresLoader = DatabaseLoader
