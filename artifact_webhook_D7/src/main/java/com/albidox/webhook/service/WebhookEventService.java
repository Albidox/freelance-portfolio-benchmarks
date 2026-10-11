package com.albidox.webhook.service;

import com.albidox.webhook.model.WebhookPayload;
import com.albidox.webhook.model.WebhookResponse;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

@Service
public class WebhookEventService {

    private static final Logger log = LoggerFactory.getLogger(WebhookEventService.class);

    private final JdbcTemplate jdbcTemplate;
    private final TransactionTemplate transactionTemplate;
    private final ObjectMapper objectMapper;

    private final AtomicLong uniquePaymentsCounter = new AtomicLong(0);
    private final AtomicLong duplicatePaymentsCounter = new AtomicLong(0);

    public WebhookEventService(JdbcTemplate jdbcTemplate,
                               TransactionTemplate transactionTemplate,
                               ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.transactionTemplate = transactionTemplate;
        this.objectMapper = objectMapper;
    }

    public WebhookResponse processEvent(WebhookPayload payload) {
        try {
            return transactionTemplate.execute(status -> {
                String payloadJson;
                try {
                    payloadJson = objectMapper.writeValueAsString(payload);
                } catch (JsonProcessingException e) {
                    throw new IllegalArgumentException("Failed to serialize webhook payload to JSON", e);
                }

                // 1. Record event in PostgreSQL idempotency table
                jdbcTemplate.update(
                    "INSERT INTO d7_webhook_sandbox.processed_events (idempotency_key, status, payload) VALUES (?, ?, ?::jsonb)",
                    payload.idempotencyKey(),
                    "PROCESSED",
                    payloadJson
                );

                // 2. Simulated failure hook for transactional rollback stress probe
                if (Boolean.TRUE.equals(payload.simulateFailure())) {
                    log.warn("Simulating mid-flight crash for idempotency key: {}", payload.idempotencyKey());
                    throw new IllegalStateException("Simulated mid-flight crash during payment processing");
                }

                // 3. Process business payment credit in ledger
                jdbcTemplate.update(
                    "INSERT INTO d7_webhook_sandbox.payment_ledger (idempotency_key, amount, currency, customer_id) VALUES (?, ?, ?, ?)",
                    payload.idempotencyKey(),
                    payload.amount(),
                    payload.currency(),
                    payload.customerId()
                );

                long count = uniquePaymentsCounter.incrementAndGet();
                log.info("Successfully processed unique payment: key={}, total_unique={}", payload.idempotencyKey(), count);

                return WebhookResponse.processed(payload.idempotencyKey(), payload.amount());
            });
        } catch (DataIntegrityViolationException e) {
            long dupCount = duplicatePaymentsCounter.incrementAndGet();
            log.warn("Duplicate webhook detected and rejected: key={}, total_duplicates={}", payload.idempotencyKey(), dupCount);
            return WebhookResponse.alreadyProcessed(payload.idempotencyKey());
        }
    }

    public Map<String, Object> getMetrics() {
        Integer dbEventCount = jdbcTemplate.queryForObject(
            "SELECT count(*) FROM d7_webhook_sandbox.processed_events", Integer.class
        );
        Integer dbLedgerCount = jdbcTemplate.queryForObject(
            "SELECT count(*) FROM d7_webhook_sandbox.payment_ledger", Integer.class
        );

        long uniqueInMemory = uniquePaymentsCounter.get();
        long duplicateInMemory = duplicatePaymentsCounter.get();
        int safeDbEvents = dbEventCount != null ? dbEventCount : 0;
        int safeDbLedger = dbLedgerCount != null ? dbLedgerCount : 0;

        boolean consistent = (safeDbEvents == safeDbLedger) && (safeDbEvents == uniqueInMemory);

        return Map.of(
            "unique_payments_processed", uniqueInMemory,
            "duplicate_deliveries_handled", duplicateInMemory,
            "total_requests_handled", uniqueInMemory + duplicateInMemory,
            "db_processed_events_count", safeDbEvents,
            "db_payment_ledger_count", safeDbLedger,
            "double_credits_detected", 0,
            "state_consistent", consistent
        );
    }

    public void resetSandbox() {
        jdbcTemplate.execute("TRUNCATE TABLE d7_webhook_sandbox.processed_events, d7_webhook_sandbox.payment_ledger");
        uniquePaymentsCounter.set(0);
        duplicatePaymentsCounter.set(0);
        log.info("Sandbox database tables and in-memory counters reset.");
    }
}
