"""Catalog normalization and schema drift handler."""
from typing import List, Dict, Any
from src.models import ShopifyProduct, ShopifyProductVariant


class CatalogSynchronizer:
    """Normalizes raw GraphQL responses into domain models and gracefully accommodates

    GraphQL API schema drifts (e.g. inventoryQuantity vs availableQuantity).
    """

    def __init__(self):
        self.drift_warnings: List[str] = []
        self.corrupt_records_count: int = 0

    def parse_graphql_response(self, response_payload: Dict[str, Any]) -> List[ShopifyProduct]:
        products: List[ShopifyProduct] = []
        data = response_payload.get("data", {})
        if not data or "products" not in data:
            self.corrupt_records_count += 1
            return products

        edges = data["products"].get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            try:
                product_id = node.get("id", "")
                title = node.get("title", "Untitled Product")
                handle = node.get("handle", "")
                vendor = node.get("vendor", "")
                status = node.get("status", "DRAFT")

                variant_list: List[ShopifyProductVariant] = []
                variant_edges = node.get("variants", {}).get("edges", [])

                for v_edge in variant_edges:
                    v_node = v_edge.get("node", {})
                    v_id = v_node.get("id", "")
                    sku = v_node.get("sku", "")
                    price = float(v_node.get("price", 0.0))

                    if "inventoryQuantity" in v_node:
                        qty = int(v_node["inventoryQuantity"])
                    elif "availableQuantity" in v_node:
                        qty = int(v_node["availableQuantity"])
                        self.drift_warnings.append("Schema drift: availableQuantity detected")
                    else:
                        qty = 0

                    barcode = v_node.get("barcode")
                    v_title = v_node.get("title", "Default Title")
                    variant_list.append(
                        ShopifyProductVariant(
                            variant_id=v_id,
                            sku=sku,
                            price=price,
                            inventory_quantity=qty,
                            barcode=barcode,
                            title=v_title,
                        )
                    )

                products.append(
                    ShopifyProduct(
                        product_id=product_id,
                        title=title,
                        handle=handle,
                        vendor=vendor,
                        status=status,
                        variants=variant_list,
                    )
                )
            except Exception:
                self.corrupt_records_count += 1

        return products
