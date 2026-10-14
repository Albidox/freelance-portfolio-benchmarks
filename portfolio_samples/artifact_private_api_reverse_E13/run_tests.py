"""Standalone deterministic test harness for E13 Private API Reverse Engineering with 26 assertions.
Runs natively on Windows without Linux shell dependencies.
Strict zero em dash policy enforced.
"""
import tracemalloc
import time
import os
import sys
import json

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.models import (
    DevicePlatform,
    DeviceFingerprint,
    ApiSignatureRequest,
    SessionCredentials,
    ExtractedEntityRecord,
    HarvestStatus,
    TrafficIntercept,
    BearerToken,
    ExtractedEndpoint,
    ReplayResponse,
    RequestAuthType
)
from src.config import PrivateApiConfig
from src.signer import MobileRequestSigner
from src.session_manager import SessionManager
from src.api_client import PrivateAPIClient, CircuitBreakerState
from src.data_extractor import DataExtractor
from src.storage import PrivateApiStorage
from src.traffic_analyzer import TrafficAnalyzer
from src.header_impersonator import HeaderImpersonator
from src.api_replay_engine import ApiReplayEngine
from src.db import DatabaseManager


def test_models_and_fingerprints():
    print("Testing models and TLS fingerprint profiles...")
    fp = DeviceFingerprint(
        platform=DevicePlatform.ANDROID,
        os_version="Android 14",
        app_version="4.28.1",
        device_id="dev_pixel_8_test",
        user_agent="Dalvik/2.1.0",
        ja3_fingerprint="771,4865-4866,0-23,29-23,0",
        ja4_fingerprint="t13d1516h2_test"
    )
    headers = fp.to_headers()
    
    # Assertion 1: Device ID in headers
    assert headers["X-Device-Id"] == "dev_pixel_8_test", "Device ID must match"
    
    # Assertion 2: Platform header matching
    assert headers["X-Device-Platform"] == "ANDROID", "Device platform must match"

    creds = SessionCredentials(
        access_token="initial_token_xyz",
        expires_at_epoch=time.time() + 300.0
    )
    # Assertion 3: Active token validity
    assert creds.is_expired() is False, "Fresh token must not be expired"

    expired_creds = SessionCredentials(
        access_token="expired_token_abc",
        expires_at_epoch=time.time() - 10.0
    )
    # Assertion 4: Expired token detection
    assert expired_creds.is_expired() is True, "Outdated token must be detected as expired"


def test_cryptographic_signer():
    print("Testing cryptographic signature engine...")
    signer = MobileRequestSigner(api_secret="secret_key_9988", salt_prefix="SALT_TEST")
    
    # Assertion 5: Monotonic nonce length
    nonce1 = signer.generate_nonce()
    assert len(nonce1) == 16, "Nonce must be 16 characters hex"
    
    # Assertion 6: Nonce randomness
    nonce2 = signer.generate_nonce()
    assert nonce1 != nonce2, "Consecutive nonces must be unique"

    req = ApiSignatureRequest(
        method="POST",
        endpoint_path="/api/v2/user/profile",
        timestamp_epoch=1700000000,
        nonce="abc123nonce",
        payload_body='{"filter":"active"}',
        api_secret="secret_key_9988"
    )
    
    # Assertion 7: Canonical string formatting
    canonical = req.to_canonical_string()
    assert canonical == 'POST|/api/v2/user/profile|1700000000|abc123nonce|{"filter":"active"}'

    sig = signer.compute_signature(req)
    # Assertion 8: Signature verification
    assert signer.verify_signature(req, sig) is True, "Signature must verify against expected calculation"

    # Assertion 9: Signature tamper rejection
    tampered_req = ApiSignatureRequest(
        method="POST",
        endpoint_path="/api/v2/user/profile",
        timestamp_epoch=1700000000,
        nonce="abc123nonce",
        payload_body='{"filter":"tampered"}',
        api_secret="secret_key_9988"
    )
    assert signer.verify_signature(tampered_req, sig) is False, "Tampered payload must fail verification"


def test_session_manager_and_tls():
    print("Testing session manager and TLS impersonation...")
    sm = SessionManager(default_platform=DevicePlatform.IOS)
    
    # Assertion 10: Platform initialization
    assert sm.device.platform == DevicePlatform.IOS, "Session manager must initialize requested platform"
    
    # Assertion 11: JA3 fingerprint populated
    assert sm.device.ja3_fingerprint.startswith("771,"), "JA3 fingerprint must conform to standard TLS format"

    sm.update_cookie("session_id", "sess_9901")
    sm.update_cookie("cf_clearance", "cf_token_val")
    # Assertion 12: Cookie header assembly
    cookie_hdr = sm.get_cookie_header()
    assert "session_id=sess_9901" in cookie_hdr, "Cookie header must contain session_id"
    assert "cf_clearance=cf_token_val" in cookie_hdr, "Cookie header must contain cf_clearance"

    # Assertion 13: Auto-refresh session token
    refreshed = sm.refresh_session_if_needed()
    assert refreshed is True, "Session refresh must return True"
    assert sm.credentials is not None, "Credentials must be populated after refresh"
    assert sm.credentials.access_token.startswith("jwt_access_"), "Generated token must start with prefix"


def test_api_client_resilience():
    print("Testing API client backoff and circuit breaker...")
    config = PrivateApiConfig(circuit_breaker_threshold=3, circuit_breaker_recovery_seconds=0.5)
    client = PrivateAPIClient(config=config)
    
    # Assertion 14: Initial state CLOSED
    assert client.state == CircuitBreakerState.CLOSED, "Initial circuit state must be CLOSED"

    # Assertion 15: Exponential backoff calculation
    delay_0 = client.calculate_backoff_delay(0)
    delay_3 = client.calculate_backoff_delay(3)
    assert delay_0 >= 0.5, "Base delay must be at least 0.5"
    assert delay_3 >= delay_0, "Backoff delay must increase with retry attempts"

    # Simulate 3 consecutive 500 errors to trip circuit breaker
    client.execute_request_cycle("GET", "/api/item/1", {}, simulated_status_code=500)
    client.execute_request_cycle("GET", "/api/item/2", {}, simulated_status_code=500)
    client.execute_request_cycle("GET", "/api/item/3", {}, simulated_status_code=500)
    
    # Assertion 16: Circuit tripped to OPEN
    assert client.state == CircuitBreakerState.OPEN, "Circuit breaker must trip to OPEN after 3 failures"
    
    # Assertion 17: Request blocked during OPEN
    status, res = client.execute_request_cycle("GET", "/api/item/4", {})
    assert status == HarvestStatus.CIRCUIT_OPEN, "Requests must be blocked when circuit is OPEN"

    # Wait for circuit recovery window
    time.sleep(0.6)
    
    # Assertion 18: Success transitions back to CLOSED
    ok_payload = json.dumps({"status": "ok", "id": "item_99"})
    status, res = client.execute_request_cycle("GET", "/api/item/5", {}, simulated_status_code=200, simulated_response_body=ok_payload)
    assert status == HarvestStatus.SUCCESS, "Successful recovery request must succeed"
    assert client.state == CircuitBreakerState.CLOSED, "Circuit breaker must transition back to CLOSED"


def test_schema_drift_and_quarantine():
    print("Testing schema drift extractor and quarantine logic...")
    extractor = DataExtractor()

    # Case 1: Standard format
    std_data = {"id": "user_101", "name": "Alice"}
    success, rec, drifted = extractor.extract_record("/api/user", std_data, "USER")
    # Assertion 19: Standard record extraction
    assert success is True, "Standard payload extraction must succeed"
    assert rec is not None, "Extracted record must not be None"
    assert rec.entity_id == "user_101", "Extracted ID must match"
    assert drifted is False, "Standard payload should not be flagged as drifted"

    # Case 2: Schema drift with 'data' container wrapper
    wrapped_data = {"status": "success", "data": {"user_id": "user_202", "name": "Bob"}}
    success, rec, drifted = extractor.extract_record("/api/user", wrapped_data, "USER")
    # Assertion 20: Schema drift detection and unwrapping
    assert success is True, "Wrapped payload extraction must succeed"
    assert rec is not None, "Wrapped record must not be None"
    assert rec.entity_id == "user_202", "Unwrapped user_id must be resolved"
    assert drifted is True, "Wrapped payload must be identified as schema drift"

    # Case 3: Corrupted payload missing primary key
    corrupted_data = {"status": "error", "message": "unauthorized missing identity"}
    success, rec, _ = extractor.extract_record("/api/user", corrupted_data, "USER")
    # Assertion 21: Corrupted record rejected and quarantined
    assert success is False, "Malformed payload must fail extraction"
    assert len(extractor.quarantine_bin) == 1, "Quarantine bin must hold exactly 1 record"
    assert extractor.quarantine_bin[0]["reason"] == "missing_primary_id", "Quarantine reason must match"


def test_dual_tier_storage():
    print("Testing dual-tier storage (SQLite WAL + PostgreSQL 18)...")
    db_file = os.path.join(CURRENT_DIR, "test_run_e13_audit.db")
    if os.path.exists(db_file):
        os.remove(db_file)

    config = PrivateApiConfig(sqlite_db_path=db_file)
    storage = PrivateApiStorage(config=config)
    
    record = ExtractedEntityRecord(
        entity_id="entity_corp_884",
        entity_type="ENTERPRISE_ORG",
        source_endpoint="/api/v2/orgs",
        payload={"tier": "enterprise", "seats": 500}
    )
    storage.store_entity(record)

    # Assertion 22: SQLite retrieval matches stored entity
    retrieved = storage.get_entity("entity_corp_884")
    assert retrieved is not None, "Stored entity must be retrievable"
    assert retrieved["entity_type"] == "ENTERPRISE_ORG", "Entity type must match"
    
    # Assertion 23: Payload JSON roundtrip
    assert retrieved["payload"]["seats"] == 500, "Payload contents must match exactly"

    # Assertion 24: Non-existent entity returns None
    assert storage.get_entity("non_existent_key") is None, "Non-existent entity must return None"

    # Assertion 25: PostgreSQL initialization check returns boolean safely
    pg_status = storage.init_postgres_schema()
    assert isinstance(pg_status, bool), "PostgreSQL initialization check must return boolean"

    storage.close()
    if os.path.exists(db_file):
        os.remove(db_file)


def test_extended_components():
    print("Testing extended modules: TrafficAnalyzer, HeaderImpersonator, ApiReplayEngine, DatabaseManager...")
    
    # Test TrafficAnalyzer HTTP/2 frames and hidden authorization
    analyzer = TrafficAnalyzer()
    frame_headers = {
        ":method": "POST",
        ":path": "/api/v3/checkout?cart_id=123&currency=USD",
        ":authority": "mobile.target.com",
        ":scheme": "https",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyXzk5OSJ9.signature",
        "x-app-version": "4.28.1",
        "content-type": "application/json"
    }
    intercept = analyzer.decode_http2_headers_frame("flow_001", frame_headers)
    assert intercept.method == "POST"
    assert intercept.server_host == "mobile.target.com"
    assert len(analyzer.discovered_tokens) == 1
    token = analyzer.discovered_tokens[0]
    assert token.token_type == "Bearer"
    assert token.claims.get("sub") == "user_999"
    assert "POST:/api/v3/checkout" in analyzer.cataloged_endpoints

    # Test HeaderImpersonator
    impersonator = HeaderImpersonator(DevicePlatform.SPA_WEB)
    web_headers = impersonator.generate_headers(target_host="spa.target.com", bearer_token="token_test")
    assert impersonator.verify_turnstile_compliance(web_headers) is True
    assert "sec-ch-ua" in web_headers

    # Test ApiReplayEngine
    replay_engine = ApiReplayEngine(tokens=["t1", "t2"])
    mock_resp = (200, {"status": "success", "data": {"items": [1, 2, 3]}})
    res = replay_engine.replay_request_sync("GET", "/api/v3/items", mock_response=mock_resp)
    assert res.success is True
    assert res.status_code == 200

    # Test DatabaseManager request logging and PostgreSQL schema
    db_mgr = DatabaseManager()
    schema_ok = db_mgr.init_schema()
    assert isinstance(schema_ok, bool)
    if schema_ok:
        log_ok = db_mgr.log_request("GET", "/api/v3/items", 200, 1.25, {"user-agent": "test"})
        assert log_ok is True
    db_mgr.close()


def main():
    tracemalloc.start()
    start_time = time.time()
    print("=" * 70)
    print("Starting Deterministic Test Suite: Artifact E13 (26 Assertions)")
    print("=" * 70)

    test_models_and_fingerprints()
    test_cryptographic_signer()
    test_session_manager_and_tls()
    test_api_client_resilience()
    test_schema_drift_and_quarantine()
    test_dual_tier_storage()
    test_extended_components()

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    duration = time.time() - start_time
    peak_mb = peak_mem / (1024 * 1024)

    # Assertion 26: Peak memory consumption under 250 MB ceiling
    assert peak_mb < 250.0, f"Memory ceiling exceeded: {peak_mb:.2f} MB"

    print("=" * 70)
    print(f"ALL 26 ASSERTIONS PASSED in {duration:.3f}s")
    print(f"Peak Memory Footprint: {peak_mb:.2f} MB (Ceiling: 250.00 MB)")
    print("=" * 70)


if __name__ == "__main__":
    main()
