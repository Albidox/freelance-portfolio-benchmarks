package com.albidox.qa.model;

import java.math.BigDecimal;
import java.time.OffsetDateTime;

public record Order(
        Long id,
        Long customerId,
        String status,
        BigDecimal totalAmount,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {}
