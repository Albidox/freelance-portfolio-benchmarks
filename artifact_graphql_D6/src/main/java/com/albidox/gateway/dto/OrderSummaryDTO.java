package com.albidox.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import java.math.BigDecimal;

@Schema(description = "Aggregated order summary retrieved from upstream GraphQL service with zero over-fetching")
public record OrderSummaryDTO(
        @Schema(description = "Unique order identifier", example = "ORD-1001")
        String orderId,

        @Schema(description = "Customer full name resolved from nested User entity", example = "Alice Vance")
        String customerName,

        @Schema(description = "Total monetary order amount", example = "249.99")
        BigDecimal totalAmount,

        @Schema(description = "Current lifecycle state of the order", example = "CONFIRMED")
        String status,

        @Schema(description = "Total count of distinct line items in the order", example = "3")
        int lineItemCount
) {
}
