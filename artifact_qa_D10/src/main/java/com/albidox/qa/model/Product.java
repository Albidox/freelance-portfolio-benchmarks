package com.albidox.qa.model;

import java.math.BigDecimal;
import java.time.OffsetDateTime;

public record Product(
        Long id,
        String sku,
        String name,
        BigDecimal price,
        Integer stockQuantity,
        OffsetDateTime createdAt
) {}
