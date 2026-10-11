package com.albidox.webhook.controller;

import com.albidox.webhook.model.WebhookPayload;
import com.albidox.webhook.model.WebhookResponse;
import com.albidox.webhook.service.WebhookEventService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/webhooks")
public class WebhookController {

    private final WebhookEventService webhookEventService;

    public WebhookController(WebhookEventService webhookEventService) {
        this.webhookEventService = webhookEventService;
    }

    @PostMapping("/payments")
    public ResponseEntity<WebhookResponse> handlePaymentWebhook(
            @RequestHeader("X-Signature") String signature,
            @RequestHeader("X-Timestamp") String timestamp,
            @RequestBody WebhookPayload payload) {

        try {
            WebhookResponse response = webhookEventService.processEvent(payload);
            return ResponseEntity.ok(response);
        } catch (IllegalStateException e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(new WebhookResponse("failed", payload.idempotencyKey(), null, e.getMessage(), null));
        }
    }

    @GetMapping("/metrics")
    public ResponseEntity<Map<String, Object>> getMetrics() {
        return ResponseEntity.ok(webhookEventService.getMetrics());
    }

    @PostMapping("/reset")
    public ResponseEntity<Map<String, String>> resetSandbox() {
        webhookEventService.resetSandbox();
        return ResponseEntity.ok(Map.of("status", "reset_completed"));
    }
}
