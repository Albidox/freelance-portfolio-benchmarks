package com.albidox.webhook.model;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.math.BigDecimal;
import java.time.Instant;

public record WebhookResponse(
    @JsonProperty("status")
    String status,

    @JsonProperty("idempotency_key")
    String idempotencyKey,

    @JsonProperty("amount")
    BigDecimal amount,

    @JsonProperty("message")
    String message,

    @JsonProperty("timestamp")
    String timestamp
) {
    public static WebhookResponse processed(String idempotencyKey, BigDecimal amount) {
        return new WebhookResponse(
            "processed",
            idempotencyKey,
            amount,
            "Payment processed successfully",
            Instant.now().toString()
        );
    }

    public static WebhookResponse alreadyProcessed(String idempotencyKey) {
        return new WebhookResponse(
            "already_processed",
            idempotencyKey,
            null,
            "Event has already been processed",
            Instant.now().toString()
        );
    }
}
