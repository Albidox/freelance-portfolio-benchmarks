package com.albidox.qa.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;

public record CreateProductRequest(
        @NotBlank(message = "Product SKU is required")
        String sku,

        @NotBlank(message = "Product name is required")
        String name,

        @NotNull(message = "Product price is required")
        @DecimalMin(value = "0.00", message = "Product price must be non-negative")
        BigDecimal price,

        @NotNull(message = "Stock quantity is required")
        @Min(value = 0, message = "Stock quantity must be non-negative")
        Integer stockQuantity
) {}
