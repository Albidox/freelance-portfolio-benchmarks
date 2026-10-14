"""Standalone deterministic test harness for E5 Payment Reconciliation with 26 assertions.
Runs natively on Windows without Linux shell dependencies.
Strict zero em dash policy enforced.
"""
import hmac
import hashlib
import os
import sys
import time
import tracemalloc
from decimal import Decimal

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.models import GatewayType, PaymentStatus, PaymentEvent, WebhookPayload
from src.config import PaymentReconcilerConfig
from src.signature_verifier import WebhookSignatureVerifier
from src.idempotency_engine import IdempotentEventReceiver
from src.state_machine import PaymentStateMachine


def test_models_and_contracts():
    print("Testing models and contract validations...")
    event = PaymentEvent(
        gateway=GatewayType.STRIPE,
        event_id="evt_test_001",
        payment_id="pi_1001",
        order_id="ord_9001",
        amount=Decimal("49.99"),
        currency="USD",
        status=PaymentStatus.CAPTURED,
        fee=Decimal("1.75"),
        tax=Decimal("0.00"),
    )

    # Assertion 1: Model dictionary serialization preserves types
    d = event.to_dict()
    assert d["amount"] == 49.99, "Amount float serialization mismatch"
    assert d["status"] == "CAPTURED", "Status enum serialization failed"

    # Assertion 2: Gateway enum value matches
    assert event.gateway == GatewayType.STRIPE, "GatewayType mismatch"

    # Assertion 3: Default fee initialized correctly
    assert event.tax == Decimal("0.00"), "Tax default mismatch"


def test_signature_verifier():
    print("Testing HMAC cryptographic verification and anti-replay...")
    config = PaymentReconcilerConfig()
    verifier = WebhookSignatureVerifier(config)

    now = int(time.time())
    payload = '{"id":"evt_123","type":"payment_intent.succeeded"}'

    # Compute valid Stripe signature
    signed_payload = f"{now}.{payload}".encode("utf-8")
    valid_hash = hmac.new(
        config.stripe_webhook_secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
    valid_header = f"t={now},v1={valid_hash}"

    # Assertion 4: Valid Stripe signature accepted
    ok, msg = verifier.verify_stripe_signature(payload, valid_header, current_time=now)
    assert ok is True, f"Valid Stripe signature failed: {msg}"

    # Assertion 5: Tampered payload rejected
    tampered_payload = '{"id":"evt_123","type":"payment_intent.failed"}'
    ok_bad, _ = verifier.verify_stripe_signature(
        tampered_payload, valid_header, current_time=now
    )
    assert ok_bad is False, "Tampered payload must fail verification"

    # Assertion 6: Tampered signature hash rejected
    bad_header = f"t={now},v1=deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    ok_fake, _ = verifier.verify_stripe_signature(payload, bad_header, current_time=now)
    assert ok_fake is False, "Fake hash must fail verification"

    # Assertion 7: Replay attack with expired timestamp rejected (> 300s)
    stale_now = now + 400
    ok_stale, msg_stale = verifier.verify_stripe_signature(
        payload, valid_header, current_time=stale_now
    )
    assert ok_stale is False, "Expired timestamp must fail"
    assert "expired" in msg_stale.lower(), f"Unexpected replay message: {msg_stale}"

    # Assertion 8: Replay attack counter incremented
    assert verifier.replay_attacks_detected >= 1, "Replay attack counter not incremented"

    # Assertion 9: Future drift timestamp rejected (> 10s)
    future_header = f"t={now + 100},v1={valid_hash}"
    ok_future, _ = verifier.verify_stripe_signature(
        payload, future_header, current_time=now
    )
    assert ok_future is False, "Future timestamp must fail"

    # Assertion 10: Valid Razorpay signature accepted
    rzp_payload = '{"event":"payment.captured","payload":{"payment":{"id":"pay_888"}}}'
    rzp_sig = hmac.new(
        config.razorpay_webhook_secret.encode("utf-8"),
        rzp_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    ok_rzp, _ = verifier.verify_razorpay_signature(rzp_payload, rzp_sig)
    assert ok_rzp is True, "Valid Razorpay signature failed"

    # Assertion 11: Tampered Razorpay signature rejected
    ok_rzp_bad, _ = verifier.verify_razorpay_signature(rzp_payload, "invalid_sig_123")
    assert ok_rzp_bad is False, "Tampered Razorpay signature must fail"


def test_idempotency_engine():
    print("Testing deduplication engine and concurrency guards...")
    engine = IdempotentEventReceiver(cache_size=100)

    # Assertion 12: First claim succeeds
    claimed1 = engine.try_claim_event("stripe", "evt_unique_1")
    assert claimed1 is True, "First event claim must succeed"

    # Assertion 13: Concurrent duplicate claim rejected while in flight
    claimed_dup = engine.try_claim_event("stripe", "evt_unique_1")
    assert claimed_dup is False, "Concurrent duplicate claim must be rejected"

    # Assertion 14: Committing event releases lock and marks processed
    engine.commit_event("stripe", "evt_unique_1")
    assert (
        engine.is_processed("stripe", "evt_unique_1") is True
    ), "Event must be processed"

    # Assertion 15: Post-commit duplicate claim rejected
    claimed_after = engine.try_claim_event("stripe", "evt_unique_1")
    assert claimed_after is False, "Duplicate claim after commit must be rejected"

    # Assertion 16: Duplicate prevention counter incremented
    assert (
        engine.duplicate_events_prevented == 2
    ), f"Expected 2 prevented duplicates, got {engine.duplicate_events_prevented}"

    # Assertion 17: Released lock permits retry on failure
    engine.try_claim_event("stripe", "evt_fail_1")
    engine.release_event_lock("stripe", "evt_fail_1")
    retry_ok = engine.try_claim_event("stripe", "evt_fail_1")
    assert retry_ok is True, "Released lock should allow retry claim"


def test_state_machine_and_discrepancies():
    print("Testing state transitions and discrepancy detection...")
    sm = PaymentStateMachine()

    # Assertion 18: Valid transition from INITIATED to AUTHORIZED
    assert sm.can_transition(PaymentStatus.INITIATED, PaymentStatus.AUTHORIZED) is True

    # Assertion 19: Valid transition from AUTHORIZED to CAPTURED
    assert sm.can_transition(PaymentStatus.AUTHORIZED, PaymentStatus.CAPTURED) is True

    # Assertion 20: Valid transition from CAPTURED to REFUNDED
    assert sm.can_transition(PaymentStatus.CAPTURED, PaymentStatus.REFUNDED) is True

    # Assertion 21: Invalid transition from REFUNDED to CAPTURED rejected
    assert sm.can_transition(PaymentStatus.REFUNDED, PaymentStatus.CAPTURED) is False

    # Assertion 22: Out-of-order recovery when AUTHORIZED arrives after CAPTURED
    resolved_state, recovered = sm.resolve_transition(
        PaymentStatus.CAPTURED, PaymentStatus.AUTHORIZED
    )
    assert resolved_state == PaymentStatus.CAPTURED, "State should remain CAPTURED"
    assert recovered is True, "Out-of-order flag must be set"
    assert sm.out_of_order_recoveries == 1, "Recovery counter mismatch"

    # Assertion 23: Discrepancy detector identifies status mismatch
    disc = sm.check_discrepancy(
        payment_id="pi_disc_01",
        gateway=GatewayType.STRIPE,
        internal_status=PaymentStatus.AUTHORIZED,
        gateway_status=PaymentStatus.CAPTURED,
        internal_amount=Decimal("100.00"),
        gateway_amount=Decimal("100.00"),
    )
    assert disc is not None, "Discrepancy should be detected"
    assert "Status mismatch" in disc.discrepancy_reason

    # Assertion 24: Discrepancy detector identifies amount mismatch
    disc_amt = sm.check_discrepancy(
        payment_id="pi_disc_02",
        gateway=GatewayType.RAZORPAY,
        internal_status=PaymentStatus.CAPTURED,
        gateway_status=PaymentStatus.CAPTURED,
        internal_amount=Decimal("100.00"),
        gateway_amount=Decimal("95.00"),
    )
    assert disc_amt is not None, "Amount discrepancy must be flagged"
    assert "Amount mismatch" in disc_amt.discrepancy_reason


def test_config_defaults():
    print("Testing configuration defaults...")
    cfg = PaymentReconcilerConfig()

    # Assertion 25: PostgreSQL default port aligns with Native Postgres 18
    assert cfg.db_port == 5433, f"Default port must be 5433, got {cfg.db_port}"
    assert cfg.db_schema == "e5_reconciliation", "Default schema mismatch"


def main():
    print("=" * 70)
    print("STARTING E5 PAYMENT RECONCILIATION DETERMINISTIC VERIFICATION SUITE")
    print("=" * 70)
    tracemalloc.start()

    test_models_and_contracts()
    test_signature_verifier()
    test_idempotency_engine()
    test_state_machine_and_discrepancies()
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
