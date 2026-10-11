package com.albidox.qa.model;

import java.math.BigDecimal;

public record OrderItem(
        Long id,
        Long orderId,
        Long productId,
        Integer quantity,
        BigDecimal unitPrice,
        BigDecimal subtotal
) {}
