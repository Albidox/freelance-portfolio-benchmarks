"""Competitive pricing parser, multi-offer aggregator, and Buy Box state evaluator."""

from typing import Dict, Any, List, Optional
from decimal import Decimal
from src.models import CompetitiveOffer, BuyBoxSnapshot


class ASINTracker:
    """Parses SP-API pricing responses and extracts Buy Box winner metadata."""

    def __init__(self, our_seller_id: str = "A3OURSELLERID"):
        self.our_seller_id = our_seller_id
        self.suppressed_buybox_count: int = 0
        self.schema_drift_detected: bool = False

    def parse_competitive_pricing(
        self, asin: str, marketplace_id: str, payload: Dict[str, Any]
    ) -> BuyBoxSnapshot:
        """Parse getCompetitivePricing payload and determine Buy Box state."""
        offers_data = payload.get("offers") or payload.get("CompetitivePricing", {}).get("CompetitivePrices", [])

        # Check for schema drift
        if "offers" not in payload and "CompetitivePricing" not in payload:
            self.schema_drift_detected = True

        parsed_offers: List[CompetitiveOffer] = []
        for item in offers_data:
            seller_id = item.get("sellerId") or item.get("SellerId", "UNKNOWN")
            is_winner = item.get("isBuyBoxWinner", False) or (item.get("CompetitivePriceId") == "1")

            # Extract price components
            price_node = item.get("price") or item.get("Price", {})
            listing_str = str(
                price_node.get("listingPrice")
                or price_node.get("LandedPrice", {}).get("Amount", "0.00")
            )
            shipping_str = str(
                price_node.get("shipping")
                or price_node.get("Shipping", {}).get("Amount", "0.00")
            )

            try:
                listing_price = Decimal(listing_str)
                shipping_price = Decimal(shipping_str)
            except Exception:
                listing_price = Decimal("0.00")
                shipping_price = Decimal("0.00")

            is_fba = item.get("isFulfilledByAmazon", False) or item.get("FulfillmentChannel") == "Amazon"
            is_prime = item.get("isPrime", False)

            parsed_offers.append(
                CompetitiveOffer(
                    seller_id=seller_id,
                    listing_price=listing_price,
                    shipping_price=shipping_price,
                    is_buybox_winner=is_winner,
                    is_fulfilled_by_amazon=is_fba,
                    is_prime=is_prime,
                )
            )

        winner = next((o for o in parsed_offers if o.is_buybox_winner), None)

        has_winner = winner is not None
        is_our_winner = winner.seller_id == self.our_seller_id if winner else False
        winner_id = winner.seller_id if winner else None
        winner_price = winner.landed_price if winner else None

        # Buy Box suppression occurs when offers exist but none won the Buy Box
        is_suppressed = len(parsed_offers) > 0 and not has_winner
        if is_suppressed:
            self.suppressed_buybox_count += 1

        return BuyBoxSnapshot(
            asin=asin,
            marketplace_id=marketplace_id,
            has_buybox_winner=has_winner,
            is_our_seller_winner=is_our_winner,
            winner_seller_id=winner_id,
            winner_landed_price=winner_price,
            total_competitive_offers=len(parsed_offers),
            is_suppressed=is_suppressed,
        )
