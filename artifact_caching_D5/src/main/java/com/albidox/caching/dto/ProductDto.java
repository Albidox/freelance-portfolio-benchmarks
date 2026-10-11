package com.albidox.caching.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.math.BigDecimal;
import java.time.OffsetDateTime;

@JsonIgnoreProperties(ignoreUnknown = true)
public record ProductDto(
        Long id,
        String sku,
        String name,
        String description,
        String category,
        BigDecimal price,
        Integer stockQuantity,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt,
        String manufacturer
) {
    public static final Long NULL_SENTINEL_ID = -1L;

    public ProductDto(
            Long id,
            String sku,
            String name,
            String description,
            String category,
            BigDecimal price,
            Integer stockQuantity,
            OffsetDateTime createdAt,
            OffsetDateTime updatedAt
    ) {
        this(id, sku, name, description, category, price, stockQuantity, createdAt, updatedAt, "Enterprise Corp");
    }

    public static ProductDto nullSentinel(String sku) {
        return new ProductDto(
                NULL_SENTINEL_ID,
                sku,
                "NOT_FOUND",
                "NULL_OBJECT_SENTINEL",
                "NONE",
                BigDecimal.ZERO,
                0,
                OffsetDateTime.now(),
                OffsetDateTime.now(),
                "NONE"
        );
    }

    public boolean isNullSentinel() {
        return Long.valueOf(NULL_SENTINEL_ID).equals(id);
    }
}
