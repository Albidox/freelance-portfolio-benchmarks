package com.albidox.qa.model;

import java.time.OffsetDateTime;

public record Customer(
        Long id,
        String name,
        String email,
        String status,
        OffsetDateTime createdAt
) {}
