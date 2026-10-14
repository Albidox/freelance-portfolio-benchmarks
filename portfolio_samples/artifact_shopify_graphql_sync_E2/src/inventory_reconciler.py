"""Real-time inventory level reconciler and delta calculation."""
from typing import List, Dict
from src.models import ShopifyProductVariant, InventoryDelta


class InventoryReconciler:
    """Computes exact inventory discrepancies between local warehouse balances

    and remote Shopify inventory levels.
    """

    def __init__(self):
        self.discrepancies_detected: int = 0

    def compute_deltas(
        self,
        local_inventory: Dict[str, int],
        remote_variants: List[ShopifyProductVariant],
    ) -> List[InventoryDelta]:
        """Compute deltas for a batch of variants against local inventory balances."""
        deltas: List[InventoryDelta] = []
        for variant in remote_variants:
            sku = variant.sku
            remote_qty = variant.inventory_quantity
            local_qty = local_inventory.get(sku, remote_qty)

            diff = local_qty - remote_qty
            requires_sync = diff != 0
            if requires_sync:
                self.discrepancies_detected += 1

            deltas.append(
                InventoryDelta(
                    sku=sku,
                    variant_id=variant.variant_id,
                    local_quantity=local_qty,
                    remote_quantity=remote_qty,
                    delta=diff,
                    requires_sync=requires_sync,
                )
            )
        return deltas
