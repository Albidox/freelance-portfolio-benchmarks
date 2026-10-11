package com.albidox.security.dto;

import java.time.Instant;
import java.util.Map;

public record ApiResponse(
        boolean success,
        String message,
        Map<String, Object> data,
        Instant timestamp
) {
    public static ApiResponse of(String message, Map<String, Object> data) {
        return new ApiResponse(true, message, data, Instant.now());
    }

    public static ApiResponse of(String message) {
        return new ApiResponse(true, message, Map.of(), Instant.now());
    }
}
