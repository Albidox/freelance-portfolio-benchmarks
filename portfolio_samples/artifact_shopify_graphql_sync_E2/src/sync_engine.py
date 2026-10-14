"""Bidirectional sync pipeline orchestrator between local inventory and Shopify."""
import time
import logging
from typing import Dict, List, Optional

from src.config import ShopifySyncConfig
from src.models import (
    ShopifyProduct,
    ShopifyProductVariant,
    InventoryDelta,
    SyncResult,
)
from src.graphql_client import ShopifyGraphQLClient
from src.catalog_syncer import CatalogSynchronizer
from src.inventory_reconciler import InventoryReconciler
from src.state_store import SyncStateStore
from src.db import PostgresStagingStore

logger = logging.getLogger("sync_engine")


class ShopifySyncEngine:
    """Bidirectional synchronization pipeline orchestrator.

    Coordinates GraphQL pagination, schema drift normalization,
    delta calculation against local warehouse inventory, idempotency check-pointing,
    and PostgreSQL 18 staging.
    """

    def __init__(self, config: Optional[ShopifySyncConfig] = None):
        self.config = config or ShopifySyncConfig()
        self.client = ShopifyGraphQLClient(self.config)
        self.catalog_syncer = CatalogSynchronizer()
        self.reconciler = InventoryReconciler()
        self.state_store = SyncStateStore(self.config.sqlite_state_path)
        self.db = PostgresStagingStore(self.config)

    async def sync_catalog_page(self, query: str = "{ products(first: 50) { edges { node { id } } } }") -> List[ShopifyProduct]:
        """Fetch and parse a catalog page with cursor tracking."""
        response = await self.client.execute_query(query)
        products = self.catalog_syncer.parse_graphql_response(response)
        page_info = response.get("data", {}).get("products", {}).get("pageInfo", {})
        cursor = page_info.get("endCursor")
        has_next = page_info.get("hasNextPage", False)

        if cursor:
            self.state_store.save_cursor("catalog_main", cursor, has_next, len(products))

        return products

    def reconcile_and_stage(
        self,
        products: List[ShopifyProduct],
        local_stock: Dict[str, int],
        persist_to_postgres: bool = True,
    ) -> SyncResult:
        """Reconcile remote variants against local stock balances and stage into PostgreSQL."""
        t0 = time.perf_counter()
        all_variants: List[ShopifyProductVariant] = []
        for p in products:
            all_variants.extend(p.variants)

        deltas = self.reconciler.compute_deltas(local_stock, all_variants)
        discrepancies = sum(1 for d in deltas if d.requires_sync)

        if persist_to_postgres:
            try:
                self.db.init_schema()
                self.db.persist_products(products)
                self.db.persist_deltas(deltas)
            except Exception as e:
                logger.warning(f"PostgreSQL staging skipped or errored: {e}")

        elapsed = time.perf_counter() - t0
        return SyncResult(
            total_processed=len(products),
            synced_variants=len(all_variants),
            discrepancies=discrepancies,
            cost_points_consumed=1000 - self.client.current_available_points,
            elapsed_seconds=elapsed,
        )
