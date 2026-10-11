package com.albidox.ratelimit.controller;

import com.albidox.ratelimit.config.RateLimitProperties;
import com.albidox.ratelimit.service.RateLimiterService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.Map;

@RestController
@RequestMapping("/api/v1")
public class ApiController {

    private final RateLimiterService rateLimiterService;
    private final RateLimitProperties properties;

    public ApiController(RateLimiterService rateLimiterService, RateLimitProperties properties) {
        this.rateLimiterService = rateLimiterService;
        this.properties = properties;
    }

    @GetMapping("/data")
    public ResponseEntity<Map<String, Object>> getData() {
        return ResponseEntity.ok(Map.of(
                "status", "success",
                "message", "Protected resource accessed successfully.",
                "timestamp", Instant.now().toString()
        ));
    }

    @GetMapping("/ping")
    public ResponseEntity<Map<String, Object>> ping() {
        return ResponseEntity.ok(Map.of(
                "status", "pong",
                "timestamp", Instant.now().toString()
        ));
    }

    @PostMapping("/admin/reset")
    public ResponseEntity<Map<String, Object>> reset(@RequestParam(required = false) String key) {
        if (key != null && !key.isBlank()) {
            rateLimiterService.resetKey(key);
            return ResponseEntity.ok(Map.of("message", "Key invalidated: " + key));
        }
        rateLimiterService.clearAll();
        return ResponseEntity.ok(Map.of("message", "All rate limit buckets invalidated."));
    }

    @PostMapping("/admin/simulate-failure")
    public ResponseEntity<Map<String, Object>> setSimulateFailure(@RequestParam boolean enabled) {
        properties.setSimulateFailure(enabled);
        return ResponseEntity.ok(Map.of(
                "simulateFailure", enabled,
                "failOpen", properties.isFailOpen()
        ));
    }

    @PostMapping("/admin/fail-open")
    public ResponseEntity<Map<String, Object>> setFailOpen(@RequestParam boolean enabled) {
        properties.setFailOpen(enabled);
        return ResponseEntity.ok(Map.of(
                "failOpen", enabled,
                "simulateFailure", properties.isSimulateFailure()
        ));
    }
}
