"""Data models and validation contracts for Amazon SP-API Buy Box Tracker."""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from decimal import Decimal
import time
from datetime import datetime, timezone


@dataclass
class AuthToken:
    """OAuth 2.0 Access Token received from Login with Amazon (LWA)."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0

    def __post_init__(self) -> None:
        if self.expires_at == 0.0:
            self.expires_at = self.created_at + float(self.expires_in)

    def is_expiring(self, within_seconds: int = 300, current_time: Optional[float] = None) -> bool:
        """Check if token is expiring within the specified grace period window."""
        now = current_time if current_time is not None else time.time()
        return (self.expires_at - now) <= within_seconds


@dataclass
class ASINRecord:
    """Tracked ASIN product catalog definition with price bounds."""

    asin: str
    marketplace_id: str
    title: str
    floor_price: Decimal
    ceiling_price: Decimal
    current_our_price: Decimal
    target_margin_percent: float = 15.0
    is_active: bool = True

    def validate_bounds(self) -> bool:
        """Ensure floor price is strictly positive and less than or equal to ceiling price."""
        return self.floor_price > Decimal("0.00") and self.floor_price <= self.ceiling_price


@dataclass
class AsinPricing:
    """Point-in-time pricing record for an ASIN."""

    asin: str
    marketplace_id: str
    listing_price: Decimal
    shipping_price: Decimal = Decimal("0.00")
    currency: str = "USD"
    is_fulfilled_by_amazon: bool = True
    is_prime: bool = True

    @property
    def landed_price(self) -> Decimal:
        return self.listing_price + self.shipping_price


@dataclass
class BuyBoxWinner:
    """Winner details extracted from competitive pricing summary."""

    seller_id: str
    landed_price: Decimal
    listing_price: Decimal
    shipping_price: Decimal
    is_fba: bool = True
    is_prime: bool = True


@dataclass
class CompetitiveOffer:
    """Individual competitor offer parsed from getCompetitivePricing."""

    seller_id: str
    listing_price: Decimal
    shipping_price: Decimal
    is_buybox_winner: bool
    is_fulfilled_by_amazon: bool
    is_prime: bool
    listing_condition: str = "New"

    @property
    def landed_price(self) -> Decimal:
        return self.listing_price + self.shipping_price


@dataclass
class BuyBoxSnapshot:
    """Buy Box status snapshot for an ASIN at a specific evaluation timestamp."""

    asin: str
    marketplace_id: str
    has_buybox_winner: bool
    is_our_seller_winner: bool
    winner_seller_id: Optional[str]
    winner_landed_price: Optional[Decimal]
    total_competitive_offers: int
    is_suppressed: bool = False
    captured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asin": self.asin,
            "marketplace_id": self.marketplace_id,
            "has_buybox_winner": self.has_buybox_winner,
            "is_our_seller_winner": self.is_our_seller_winner,
            "winner_seller_id": self.winner_seller_id,
            "winner_landed_price": float(self.winner_landed_price) if self.winner_landed_price is not None else None,
            "total_competitive_offers": self.total_competitive_offers,
            "is_suppressed": self.is_suppressed,
            "captured_at": self.captured_at,
        }


@dataclass
class CompetitivePricingResponse:
    """Complete competitive pricing response container."""

    asin: str
    marketplace_id: str
    status: str = "Success"
    offers: List[CompetitiveOffer] = field(default_factory=list)
    buybox_winner: Optional[BuyBoxWinner] = None
    is_suppressed: bool = False


@dataclass
class RepricingDecision:
    """Algorithmic repricing recommendation with margin boundary enforcement flags."""

    asin: str
    current_price: Decimal
    recommended_price: Decimal
    rule_name: str
    floor_enforced: bool
    ceiling_enforced: bool
    price_delta: Decimal
    decided_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
