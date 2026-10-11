package com.albidox.caching.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.math.BigDecimal;

@JsonIgnoreProperties(ignoreUnknown = true)
public record UpdateProductRequest(
        String name,
        String description,
        String category,
        BigDecimal price,
        Integer stockQuantity
) {
}
