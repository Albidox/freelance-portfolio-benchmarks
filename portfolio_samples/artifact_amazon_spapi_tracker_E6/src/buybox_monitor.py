"""Algorithmic repricing calculator with strict margin floor and ceiling guardrails."""

from decimal import Decimal
from src.models import ASINRecord, BuyBoxSnapshot, RepricingDecision


class BuyBoxMonitor:
    """Computes target repricing actions while strictly guaranteeing margin bounds."""

    def __init__(self, undercut_penny: Decimal = Decimal("0.01")):
        self.undercut_penny = undercut_penny
        self.floor_violations_blocked: int = 0
        self.ceiling_violations_blocked: int = 0

    def compute_repricing(self, asin_record: ASINRecord, snapshot: BuyBoxSnapshot) -> RepricingDecision:
        """Determine next competitive price strictly bounded by [floor_price, ceiling_price]."""
        current_price = asin_record.current_our_price
        target_price = current_price
        rule = "MAINTAIN_CURRENT"

        if snapshot.is_suppressed or not snapshot.has_buybox_winner:
            # When Buy Box is suppressed, lower slightly to regain feature status
            target_price = current_price - Decimal("0.50")
            rule = "UNSUPPRESS_SEARCH"
        elif snapshot.is_our_seller_winner:
            # We own the Buy Box: test price upward elasticity to maximize margin
            target_price = current_price + Decimal("0.10")
            rule = "OPTIMIZE_MARGIN_UPWARD"
        else:
            # Competitor owns the Buy Box: undercut by configured penny amount
            if snapshot.winner_landed_price is not None:
                target_price = snapshot.winner_landed_price - self.undercut_penny
                rule = "UNDERCUT_COMPETITOR"

        # Apply Margin Floor Guardrail
        floor_enforced = False
        if target_price < asin_record.floor_price:
            target_price = asin_record.floor_price
            floor_enforced = True
            self.floor_violations_blocked += 1

        # Apply Ceiling Guardrail
        ceiling_enforced = False
        if target_price > asin_record.ceiling_price:
            target_price = asin_record.ceiling_price
            ceiling_enforced = True
            self.ceiling_violations_blocked += 1

        delta = target_price - current_price

        return RepricingDecision(
            asin=asin_record.asin,
            current_price=current_price,
            recommended_price=target_price,
            rule_name=rule,
            floor_enforced=floor_enforced,
            ceiling_enforced=ceiling_enforced,
            price_delta=delta,
        )
