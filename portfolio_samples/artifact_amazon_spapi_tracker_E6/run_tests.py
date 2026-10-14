"""Standalone deterministic test harness for E6 Amazon SP-API Buy Box Tracker with 26 assertions.
Runs natively on Windows without Linux shell dependencies.
Strict zero em dash policy enforced.
"""
import os
import sys
import time
import tracemalloc
from decimal import Decimal

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.models import ASINRecord, CompetitiveOffer, BuyBoxSnapshot, RepricingDecision
from src.config import SPAPIConfig
from src.sp_client import AmazonSPAPIClient
from src.asin_tracker import ASINTracker
from src.buybox_monitor import BuyBoxMonitor


def test_models_and_bounds():
    print("Testing models and pricing boundary validation...")
    asin = ASINRecord(
        asin="B08N5WRWNW",
        marketplace_id="ATVPDKIKX0DER",
        title="Wireless Ergonomic Mouse",
        floor_price=Decimal("19.99"),
        ceiling_price=Decimal("49.99"),
        current_our_price=Decimal("29.99"),
    )

    # Assertion 1: Valid price bounds check passes
    assert asin.validate_bounds() is True, "Valid bounds should pass"

    # Assertion 2: Invalid negative floor price fails bounds check
    asin_bad = ASINRecord(
        asin="B08N5WRWNW",
        marketplace_id="ATVPDKIKX0DER",
        title="Broken Item",
        floor_price=Decimal("-5.00"),
        ceiling_price=Decimal("49.99"),
        current_our_price=Decimal("29.99"),
    )
    assert asin_bad.validate_bounds() is False, "Negative floor must fail"

    # Assertion 3: Floor greater than ceiling fails bounds check
    asin_inverted = ASINRecord(
        asin="B08N5WRWNW",
        marketplace_id="ATVPDKIKX0DER",
        title="Inverted Item",
        floor_price=Decimal("55.00"),
        ceiling_price=Decimal("49.99"),
        current_our_price=Decimal("50.00"),
    )
    assert asin_inverted.validate_bounds() is False, "Floor > Ceiling must fail"

    # Assertion 4: Competitive offer computes total landed price accurately
    offer = CompetitiveOffer(
        seller_id="SELLER_123",
        listing_price=Decimal("24.50"),
        shipping_price=Decimal("4.50"),
        is_buybox_winner=True,
        is_fulfilled_by_amazon=True,
        is_prime=True,
    )
    assert offer.landed_price == Decimal("29.00"), f"Landed price mismatch: {offer.landed_price}"

    # Assertion 5: Snapshot dictionary preserves types
    snap = BuyBoxSnapshot(
        asin="B08N5WRWNW",
        marketplace_id="ATVPDKIKX0DER",
        has_buybox_winner=True,
        is_our_seller_winner=False,
        winner_seller_id="SELLER_123",
        winner_landed_price=Decimal("29.00"),
        total_competitive_offers=3,
    )
    d = snap.to_dict()
    assert d["winner_landed_price"] == 29.0, "Float conversion mismatch"
    assert d["has_buybox_winner"] is True, "Boolean field mismatch"


def test_sp_client_and_sigv4():
    print("Testing LWA token management and AWS SigV4 headers...")
    cfg = SPAPIConfig()
    client = AmazonSPAPIClient(cfg)

    # Assertion 6: LWA token generated and cached
    token1 = client.get_valid_lwa_token(current_time=1000.0)
    assert token1.startswith("Atza|"), "Invalid LWA token format"
    assert client.lwa_refresh_count == 1, "Refresh count mismatch"

    # Assertion 7: Cached token reused within TTL
    token2 = client.get_valid_lwa_token(current_time=1200.0)
    assert token1 == token2, "Token should be reused within TTL"
    assert client.lwa_refresh_count == 1, "Should not refresh before TTL expiration"

    # Assertion 8: Token refreshes when expiring within 300 seconds
    token3 = client.get_valid_lwa_token(current_time=1000.0 + 3400.0)
    assert token3 != token1, "Token should refresh when near expiry"
    assert client.lwa_refresh_count == 2, "Refresh count should increment"

    # Assertion 9: SigV4 headers contain mandatory AWS authorization components
    headers = client.compute_sigv4_headers(
        method="GET",
        service="execute-api",
        host="sellingpartnerapi-na.amazon.com",
        canonical_uri="/products/pricing/v0/competitivePrice",
        query_params={"MarketplaceId": "ATVPDKIKX0DER", "Asins": "B08N5WRWNW"},
        payload="",
        timestamp_epoch=1700000000.0,
    )
    assert "Authorization" in headers, "Missing Authorization header"
    assert "AWS4-HMAC-SHA256" in headers["Authorization"], "Missing algorithm tag"
    assert "Credential=" in headers["Authorization"], "Missing credential tag"
    assert "SignedHeaders=host;x-amz-date" in headers["Authorization"], "Missing signed headers tag"

    # Assertion 10: SigV4 x-amz-access-token present
    assert "x-amz-access-token" in headers, "Missing access token header"

    # Assertion 11: Leaky bucket backoff calculation
    backoff1 = client.calculate_leaky_bucket_backoff(attempt=1)
    assert backoff1 == 1.0, f"Expected 1.0s, got {backoff1}"
    backoff3 = client.calculate_leaky_bucket_backoff(attempt=3)
    assert backoff3 == 4.0, f"Expected 4.0s, got {backoff3}"
    assert client.rate_limit_throttle_count == 2, "Throttle count mismatch"


def test_asin_tracker_and_buybox():
    print("Testing ASIN competitive parsing and Buy Box state...")
    tracker = ASINTracker(our_seller_id="A3OURSELLERID")

    # Sample payload where competitor wins
    sample_payload = {
        "offers": [
            {
                "sellerId": "COMPETITOR_99",
                "isBuyBoxWinner": True,
                "price": {"listingPrice": "25.00", "shipping": "0.00"},
                "isFulfilledByAmazon": True,
                "isPrime": True,
            },
            {
                "sellerId": "A3OURSELLERID",
                "isBuyBoxWinner": False,
                "price": {"listingPrice": "25.99", "shipping": "0.00"},
                "isFulfilledByAmazon": True,
                "isPrime": True,
            },
        ]
    }
    snap = tracker.parse_competitive_pricing("B08N5WRWNW", "ATVPDKIKX0DER", sample_payload)

    # Assertion 12: Buy Box winner detected
    assert snap.has_buybox_winner is True, "Failed to identify Buy Box winner"

    # Assertion 13: Competitor is winner
    assert snap.is_our_seller_winner is False, "Our seller should not be winner"
    assert snap.winner_seller_id == "COMPETITOR_99", "Winner seller mismatch"

    # Assertion 14: Winner price extracted correctly
    assert snap.winner_landed_price == Decimal("25.00"), "Winner price mismatch"

    # Assertion 15: Not suppressed when winner exists
    assert snap.is_suppressed is False, "Should not be suppressed when winner exists"

    # Sample payload where Buy Box is suppressed (offers exist, no winner)
    suppressed_payload = {
        "offers": [
            {
                "sellerId": "COMPETITOR_1",
                "isBuyBoxWinner": False,
                "price": {"listingPrice": "49.00", "shipping": "5.00"},
            }
        ]
    }
    snap_sup = tracker.parse_competitive_pricing("B08SUPPRESS", "ATVPDKIKX0DER", suppressed_payload)

    # Assertion 16: Suppressed Buy Box identified
    assert snap_sup.has_buybox_winner is False, "Suppressed item should have no winner"
    assert snap_sup.is_suppressed is True, "Failed to flag suppressed Buy Box"
    assert tracker.suppressed_buybox_count == 1, "Suppressed count mismatch"


def test_repricing_monitor_and_guardrails():
    print("Testing algorithmic repricing rules and margin guardrails...")
    monitor = BuyBoxMonitor(undercut_penny=Decimal("0.01"))
    asin = ASINRecord(
        asin="B08N5WRWNW",
        marketplace_id="ATVPDKIKX0DER",
        title="Wireless Mouse",
        floor_price=Decimal("20.00"),
        ceiling_price=Decimal("40.00"),
        current_our_price=Decimal("28.00"),
    )

    # Scenario A: Competitor wins at $25.00 -> Undercut to $24.99
    snap_comp = BuyBoxSnapshot(
        asin="B08N5WRWNW",
        marketplace_id="ATVPDKIKX0DER",
        has_buybox_winner=True,
        is_our_seller_winner=False,
        winner_seller_id="COMPETITOR_99",
        winner_landed_price=Decimal("25.00"),
        total_competitive_offers=2,
    )
    dec_undercut = monitor.compute_repricing(asin, snap_comp)

    # Assertion 17: Undercut rule applied
    assert dec_undercut.rule_name == "UNDERCUT_COMPETITOR", f"Expected undercut rule, got {dec_undercut.rule_name}"

    # Assertion 18: Price undercut by exactly $0.01
    assert dec_undercut.recommended_price == Decimal("24.99"), f"Expected 24.99, got {dec_undercut.recommended_price}"
    assert dec_undercut.floor_enforced is False, "Floor should not be triggered"

    # Scenario B: Competitor prices below our floor at $18.00 -> Floor Guardrail Enforced!
    snap_low = BuyBoxSnapshot(
        asin="B08N5WRWNW",
        marketplace_id="ATVPDKIKX0DER",
        has_buybox_winner=True,
        is_our_seller_winner=False,
        winner_seller_id="DUMPING_SELLER",
        winner_landed_price=Decimal("18.00"),
        total_competitive_offers=2,
    )
    dec_floor = monitor.compute_repricing(asin, snap_low)

    # Assertion 19: Margin floor guardrail prevents negative margin
    assert dec_floor.recommended_price == Decimal("20.00"), f"Floor protection failed: {dec_floor.recommended_price}"

    # Assertion 20: Floor enforced flag is True
    assert dec_floor.floor_enforced is True, "floor_enforced must be True"
    assert monitor.floor_violations_blocked == 1, "Floor violations counter mismatch"

    # Scenario C: We already own Buy Box -> Margin Expansion Upward
    snap_ours = BuyBoxSnapshot(
        asin="B08N5WRWNW",
        marketplace_id="ATVPDKIKX0DER",
        has_buybox_winner=True,
        is_our_seller_winner=True,
        winner_seller_id="A3OURSELLERID",
        winner_landed_price=Decimal("28.00"),
        total_competitive_offers=2,
    )
    dec_up = monitor.compute_repricing(asin, snap_ours)

    # Assertion 21: Upward margin testing rule applied
    assert dec_up.rule_name == "OPTIMIZE_MARGIN_UPWARD", f"Rule mismatch: {dec_up.rule_name}"
    assert dec_up.recommended_price == Decimal("28.10"), f"Price should expand by 0.10, got {dec_up.recommended_price}"

    # Scenario D: Ceiling Guardrail Enforced when near top
    asin_near_top = ASINRecord(
        asin="B08TOP",
        marketplace_id="ATVPDKIKX0DER",
        title="Top Item",
        floor_price=Decimal("20.00"),
        ceiling_price=Decimal("30.00"),
        current_our_price=Decimal("29.95"),
    )
    dec_ceil = monitor.compute_repricing(asin_near_top, snap_ours)

    # Assertion 22: Ceiling protection caps at ceiling_price
    assert dec_ceil.recommended_price == Decimal("30.00"), f"Ceiling protection failed: {dec_ceil.recommended_price}"
    assert dec_ceil.ceiling_enforced is True, "ceiling_enforced must be True"

    # Scenario E: Suppressed Buy Box triggers unsuppress search rule
    snap_suppressed = BuyBoxSnapshot(
        asin="B08N5WRWNW",
        marketplace_id="ATVPDKIKX0DER",
        has_buybox_winner=False,
        is_our_seller_winner=False,
        winner_seller_id=None,
        winner_landed_price=None,
        total_competitive_offers=2,
        is_suppressed=True,
    )
    dec_unsup = monitor.compute_repricing(asin, snap_suppressed)

    # Assertion 23: Unsuppress search rule lowers price to regain buybox
    assert dec_unsup.rule_name == "UNSUPPRESS_SEARCH", f"Rule mismatch: {dec_unsup.rule_name}"
    assert dec_unsup.recommended_price == Decimal("27.50"), f"Expected 27.50, got {dec_unsup.recommended_price}"

    # Assertion 24: Price delta computed accurately
    assert dec_unsup.price_delta == Decimal("-0.50"), f"Expected -0.50, got {dec_unsup.price_delta}"


def test_config_defaults():
    print("Testing configuration defaults...")
    cfg = SPAPIConfig()

    # Assertion 25: PostgreSQL default port aligns with Native Postgres 18
    assert cfg.db_port == 5433, f"Default port must be 5433, got {cfg.db_port}"
    assert cfg.db_schema == "e6_spapi_tracker", "Default schema mismatch"


def main():
    print("=" * 70)
    print("STARTING E6 SP-API BUY BOX TRACKER DETERMINISTIC VERIFICATION SUITE")
    print("=" * 70)
    tracemalloc.start()

    test_models_and_bounds()
    test_sp_client_and_sigv4()
    test_asin_tracker_and_buybox()
    test_repricing_monitor_and_guardrails()
    test_config_defaults()

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak_mem / (1024 * 1024)
    print(f"Memory Diagnostics: Peak memory consumed: {peak_mb:.2f} MB")

    # Assertion 26: Strict memory footprint ceiling under 250MB
    assert peak_mb < 250.0, f"Memory footprint exceeded 250MB: {peak_mb:.2f} MB"

    print("=" * 70)
    print("ALL 26 ASSERTIONS PASSED WITH ZERO MOCKS OR PHANTOM DAEMONS")
    print("=" * 70)


if __name__ == "__main__":
    main()
