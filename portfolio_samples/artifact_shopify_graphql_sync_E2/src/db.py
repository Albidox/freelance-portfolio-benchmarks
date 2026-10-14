"""PostgreSQL 18 dynamic staging schema integration for Artifact E2."""
import logging
from typing import List, Optional
import psycopg2
from psycopg2.extras import execute_values

from src.config import ShopifySyncConfig
from src.models import ShopifyProduct, InventoryDelta

logger = logging.getLogger("db_staging")


class PostgresStagingStore:
    """Manages multi-tenant catalog staging tables in PostgreSQL 18 on port 5433."""

    def __init__(self, config: Optional[ShopifySyncConfig] = None):
        self.config = config or ShopifySyncConfig()
        self.schema = self.config.db_schema

    def get_connection(self):
        return psycopg2.connect(
            host=self.config.db_host,
            port=self.config.db_port,
            user=self.config.db_user,
            password=self.config.db_password,
            dbname=self.config.db_name,
        )

    def init_schema(self) -> None:
        """Create sandbox schema and tables in PostgreSQL 18 with idempotent DDL."""
        conn = self.get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema};")
                    cur.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {self.schema}.staged_products (
                            product_id VARCHAR(128) PRIMARY KEY,
                            title VARCHAR(255) NOT NULL,
                            handle VARCHAR(255) NOT NULL,
                            vendor VARCHAR(255),
                            status VARCHAR(64),
                            variant_count INTEGER DEFAULT 0,
                            synced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    )
                    cur.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {self.schema}.staged_variants (
                            variant_id VARCHAR(128) PRIMARY KEY,
                            product_id VARCHAR(128) REFERENCES {self.schema}.staged_products(product_id) ON DELETE CASCADE,
                            sku VARCHAR(128) NOT NULL,
                            price NUMERIC(12, 2) NOT NULL,
                            inventory_quantity INTEGER NOT NULL,
                            barcode VARCHAR(64),
                            title VARCHAR(255),
                            synced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    )
                    cur.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {self.schema}.inventory_sync_deltas (
                            id SERIAL PRIMARY KEY,
                            sku VARCHAR(128) NOT NULL,
                            variant_id VARCHAR(128) NOT NULL,
                            local_quantity INTEGER NOT NULL,
                            remote_quantity INTEGER NOT NULL,
                            delta INTEGER NOT NULL,
                            requires_sync BOOLEAN NOT NULL,
                            recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    )
                    cur.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_staged_variants_sku ON {self.schema}.staged_variants(sku);"
                    )
                    cur.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_inventory_deltas_sku ON {self.schema}.inventory_sync_deltas(sku);"
                    )
        finally:
            conn.close()

    def persist_products(self, products: List[ShopifyProduct]) -> int:
        """Persist products and nested variants using atomic batch upsert."""
        if not products:
            return 0

        conn = self.get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    prod_records = [
                        (p.product_id, p.title, p.handle, p.vendor, p.status, len(p.variants))
                        for p in products
                    ]
                    execute_values(
                        cur,
                        f"""
                        INSERT INTO {self.schema}.staged_products (product_id, title, handle, vendor, status, variant_count)
                        VALUES %s
                        ON CONFLICT (product_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            handle = EXCLUDED.handle,
                            vendor = EXCLUDED.vendor,
                            status = EXCLUDED.status,
                            variant_count = EXCLUDED.variant_count,
                            synced_at = CURRENT_TIMESTAMP;
                        """,
                        prod_records,
                    )

                    var_records = []
                    for p in products:
                        for v in p.variants:
                            var_records.append(
                                (v.variant_id, p.product_id, v.sku, v.price, v.inventory_quantity, v.barcode, v.title)
                            )
                    if var_records:
                        execute_values(
                            cur,
                            f"""
                            INSERT INTO {self.schema}.staged_variants (variant_id, product_id, sku, price, inventory_quantity, barcode, title)
                            VALUES %s
                            ON CONFLICT (variant_id) DO UPDATE SET
                                sku = EXCLUDED.sku,
                                price = EXCLUDED.price,
                                inventory_quantity = EXCLUDED.inventory_quantity,
                                barcode = EXCLUDED.barcode,
                                title = EXCLUDED.title,
                                synced_at = CURRENT_TIMESTAMP;
                            """,
                            var_records,
                        )
            return len(products)
        finally:
            conn.close()

    def persist_deltas(self, deltas: List[InventoryDelta]) -> int:
        """Log inventory deltas for audit tracking."""
        if not deltas:
            return 0

        conn = self.get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    records = [
                        (d.sku, d.variant_id, d.local_quantity, d.remote_quantity, d.delta, d.requires_sync)
                        for d in deltas
                    ]
                    execute_values(
                        cur,
                        f"""
                        INSERT INTO {self.schema}.inventory_sync_deltas (sku, variant_id, local_quantity, remote_quantity, delta, requires_sync)
                        VALUES %s;
                        """,
                        records,
                    )
            return len(deltas)
        finally:
            conn.close()
