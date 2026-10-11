package com.albidox.webhook.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.math.BigDecimal;

@JsonIgnoreProperties(ignoreUnknown = true)
public record WebhookPayload(
    @JsonProperty("idempotency_key")
    String idempotencyKey,

    @JsonProperty("event_id")
    String eventId,

    @JsonProperty("event_type")
    String eventType,

    @JsonProperty("amount")
    BigDecimal amount,

    @JsonProperty("currency")
    String currency,

    @JsonProperty("customer_id")
    String customerId,

    @JsonProperty("simulate_failure")
    Boolean simulateFailure
) {
    public WebhookPayload {
        if (idempotencyKey == null || idempotencyKey.isBlank()) {
            if (eventId != null && !eventId.isBlank()) {
                idempotencyKey = eventId;
            } else {
                throw new IllegalArgumentException("idempotency_key or event_id must be provided");
            }
        }
        if (amount == null) {
            amount = BigDecimal.ZERO;
        }
        if (currency == null) {
            currency = "USD";
        }
        if (customerId == null) {
            customerId = "anonymous";
        }
        if (eventType == null) {
            eventType = "payment.succeeded";
        }
    }
}
