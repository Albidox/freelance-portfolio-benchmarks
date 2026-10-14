"""Data contracts and domain models for Shopify GraphQL synchronization."""
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


@dataclass
class ShopifyProductVariant:
    variant_id: str
    sku: str
    price: float
    inventory_quantity: int
    barcode: Optional[str] = None
    title: str = "Default Title"


@dataclass
class ShopifyProduct:
    product_id: str
    title: str
    handle: str
    vendor: str
    status: str
    variants: List[ShopifyProductVariant] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProductSyncItem:
    product_id: str
    title: str
    sku: str
    variant_id: str
    inventory_quantity: int
    price: float
    status: str = "ACTIVE"
    last_synced_at: Optional[str] = None


@dataclass
class InventoryDelta:
    sku: str
    variant_id: str
    local_quantity: int
    remote_quantity: int
    delta: int
    requires_sync: bool


@dataclass
class SyncResult:
    total_processed: int
    synced_variants: int
    discrepancies: int
    cost_points_consumed: int
    elapsed_seconds: float
    errors: List[str] = field(default_factory=list)


@dataclass
class GraphQLCostProfile:
    requested_query_cost: int
    actual_query_cost: int
    throttle_status_currently_available: int
    restore_rate: int = 50
    maximum_available: int = 1000
