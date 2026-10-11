package com.albidox.webhook;

import com.albidox.webhook.service.WebhookEventService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.HexFormat;

import static org.hamcrest.Matchers.is;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class WebhookApplicationTests {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private WebhookEventService webhookEventService;

    @Autowired
    private org.springframework.jdbc.core.JdbcTemplate jdbcTemplate;

    private static final String SECRET = "webhook-secret-key-prod-d7-secure-2026";

    @BeforeEach
    void setup() {
        webhookEventService.resetSandbox();
    }

    private String calculateSignature(String timestamp, String body) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        SecretKeySpec keySpec = new SecretKeySpec(SECRET.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
        mac.init(keySpec);
        byte[] bytes = mac.doFinal((timestamp + "." + body).getBytes(StandardCharsets.UTF_8));
        return HexFormat.of().formatHex(bytes);
    }

    @Test
    @DisplayName("Should accept valid webhook and process payment")
    void shouldProcessValidWebhook() throws Exception {
        String timestamp = String.valueOf(Instant.now().getEpochSecond());
        String body = "{\"idempotency_key\":\"evt_test_001\",\"amount\":150.00,\"currency\":\"USD\",\"customer_id\":\"cust_10\"}";
        String signature = calculateSignature(timestamp, body);

        mockMvc.perform(post("/api/v1/webhooks/payments")
                        .header("X-Timestamp", timestamp)
                        .header("X-Signature", signature)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status", is("processed")))
                .andExpect(jsonPath("$.idempotency_key", is("evt_test_001")));
    }

    @Test
    @DisplayName("Should detect duplicate idempotency key and return already_processed with HTTP 200")
    void shouldHandleDuplicateIdempotencyKey() throws Exception {
        String timestamp = String.valueOf(Instant.now().getEpochSecond());
        String body = "{\"idempotency_key\":\"evt_test_dup\",\"amount\":200.00,\"currency\":\"USD\",\"customer_id\":\"cust_20\"}";
        String signature = calculateSignature(timestamp, body);

        // First delivery
        mockMvc.perform(post("/api/v1/webhooks/payments")
                        .header("X-Timestamp", timestamp)
                        .header("X-Signature", signature)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status", is("processed")));

        // Duplicate delivery
        mockMvc.perform(post("/api/v1/webhooks/payments")
                        .header("X-Timestamp", timestamp)
                        .header("X-Signature", signature)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status", is("already_processed")))
                .andExpect(jsonPath("$.idempotency_key", is("evt_test_dup")));
    }

    @Test
    @DisplayName("Should reject request older than 300 seconds with HTTP 400")
    void shouldRejectExpiredTimestamp() throws Exception {
        long oldTimestamp = Instant.now().getEpochSecond() - 360;
        String timestampStr = String.valueOf(oldTimestamp);
        String body = "{\"idempotency_key\":\"evt_test_old\",\"amount\":50.00,\"currency\":\"USD\",\"customer_id\":\"cust_30\"}";
        String signature = calculateSignature(timestampStr, body);

        mockMvc.perform(post("/api/v1/webhooks/payments")
                        .header("X-Timestamp", timestampStr)
                        .header("X-Signature", signature)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status", is("error")));
    }

    @Test
    @DisplayName("Round 2 Probe 1: Replay attack simulation older than 300 seconds rejected with HTTP 400")
    void shouldRejectReplayAttackAfter360Seconds() throws Exception {
        long oldTimestamp = Instant.now().getEpochSecond() - 360;
        String timestampStr = String.valueOf(oldTimestamp);
        String body = "{\"idempotency_key\":\"evt_replay_probe_360\",\"amount\":125.50,\"currency\":\"USD\",\"customer_id\":\"cust_replay\"}";
        String signature = calculateSignature(timestampStr, body);

        mockMvc.perform(post("/api/v1/webhooks/payments")
                        .header("X-Timestamp", timestampStr)
                        .header("X-Signature", signature)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status", is("error")))
                .andExpect(jsonPath("$.code", is(400)))
                .andExpect(jsonPath("$.message", is("Timestamp outside allowed tolerance window (300s)")));
    }

    @Test
    @DisplayName("Round 2 Probe 2: Signature tampering fuzzing rejects 1-char flipped payload in sub-0.2ms with HTTP 401")
    void shouldRejectTamperedPayloadWithinSubPointTwoMs() throws Exception {
        String timestamp = String.valueOf(Instant.now().getEpochSecond());
        String originalBody = "{\"idempotency_key\":\"evt_fuzz_sig_01\",\"amount\":350.00,\"currency\":\"USD\",\"customer_id\":\"cust_fuzz\"}";
        String validSignature = calculateSignature(timestamp, originalBody);

        // Fuzz payload: flip 1 character in body ('350.00' -> '450.00')
        String tamperedBody = originalBody.replace("350.00", "450.00");

        // Warm up crypto engine, filter pipeline, and JIT
        for (int i = 0; i < 50; i++) {
            mockMvc.perform(post("/api/v1/webhooks/payments")
                            .header("X-Timestamp", timestamp)
                            .header("X-Signature", validSignature)
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(tamperedBody));
        }

        var mvcResult = mockMvc.perform(post("/api/v1/webhooks/payments")
                        .header("X-Timestamp", timestamp)
                        .header("X-Signature", validSignature)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(tamperedBody))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.status", is("error")))
                .andExpect(jsonPath("$.code", is(401)))
                .andExpect(jsonPath("$.message", is("Invalid HMAC signature")))
                .andReturn();

        String durationNanosHeader = mvcResult.getResponse().getHeader("X-Verification-Time-Nanos");
        org.junit.jupiter.api.Assertions.assertNotNull(durationNanosHeader, "Header X-Verification-Time-Nanos must be present");
        long verificationNanos = Long.parseLong(durationNanosHeader);
        double verificationMs = verificationNanos / 1_000_000.0;

        // Verify verification latency is within 0.2ms (200,000 ns) threshold
        org.junit.jupiter.api.Assertions.assertTrue(verificationNanos < 200_000,
                "Verification duration must be < 0.2ms (200,000 ns), actual: " + verificationNanos + " ns (" + verificationMs + " ms)");
    }

    @Test
    @DisplayName("Round 2 Probe 3: Mid-flight database crash triggers transaction rollback preventing ghost events")
    void shouldRollbackTransactionAndPreventGhostEventsOnMidFlightCrash() throws Exception {
        String idempotencyKey = "evt_crash_rollback_01";
        String timestamp = String.valueOf(Instant.now().getEpochSecond());
        String failingBody = "{\"idempotency_key\":\"" + idempotencyKey + "\",\"amount\":777.00,\"currency\":\"USD\",\"customer_id\":\"cust_crash\",\"simulate_failure\":true}";
        String signature = calculateSignature(timestamp, failingBody);

        // 1. Trigger mid-flight crash during event processing
        mockMvc.perform(post("/api/v1/webhooks/payments")
                        .header("X-Timestamp", timestamp)
                        .header("X-Signature", signature)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(failingBody))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.status", is("failed")))
                .andExpect(jsonPath("$.idempotency_key", is(idempotencyKey)));

        // 2. Verify transactional rollback in PostgreSQL: zero ghost events recorded
        Integer eventCountAfterCrash = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM d7_webhook_sandbox.processed_events WHERE idempotency_key = ?",
                Integer.class,
                idempotencyKey
        );
        Integer ledgerCountAfterCrash = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM d7_webhook_sandbox.payment_ledger WHERE idempotency_key = ?",
                Integer.class,
                idempotencyKey
        );

        org.junit.jupiter.api.Assertions.assertEquals(0, eventCountAfterCrash, "Processed events must have 0 rows after rollback");
        org.junit.jupiter.api.Assertions.assertEquals(0, ledgerCountAfterCrash, "Payment ledger must have 0 rows after rollback");

        // 3. Retry identical idempotency key without failure flag
        String recoveryTimestamp = String.valueOf(Instant.now().getEpochSecond());
        String recoveryBody = "{\"idempotency_key\":\"" + idempotencyKey + "\",\"amount\":777.00,\"currency\":\"USD\",\"customer_id\":\"cust_crash\",\"simulate_failure\":false}";
        String recoverySignature = calculateSignature(recoveryTimestamp, recoveryBody);

        mockMvc.perform(post("/api/v1/webhooks/payments")
                        .header("X-Timestamp", recoveryTimestamp)
                        .header("X-Signature", recoverySignature)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(recoveryBody))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status", is("processed")))
                .andExpect(jsonPath("$.idempotency_key", is(idempotencyKey)));

        // 4. Verify post-recovery database state: exactly 1 event and 1 ledger entry
        Integer eventCountAfterRecovery = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM d7_webhook_sandbox.processed_events WHERE idempotency_key = ?",
                Integer.class,
                idempotencyKey
        );
        Integer ledgerCountAfterRecovery = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM d7_webhook_sandbox.payment_ledger WHERE idempotency_key = ?",
                Integer.class,
                idempotencyKey
        );

        org.junit.jupiter.api.Assertions.assertEquals(1, eventCountAfterRecovery, "Processed events must have exactly 1 row after successful retry");
        org.junit.jupiter.api.Assertions.assertEquals(1, ledgerCountAfterRecovery, "Payment ledger must have exactly 1 row after successful retry");
    }
}
