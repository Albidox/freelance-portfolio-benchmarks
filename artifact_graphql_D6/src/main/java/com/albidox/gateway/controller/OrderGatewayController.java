package com.albidox.gateway.controller;

import com.albidox.gateway.client.GraphQLUpstreamClient;
import com.albidox.gateway.dto.OrderSummaryDTO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.MediaType;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/orders")
@Tag(name = "Order Gateway", description = "REST API translating complex upstream GraphQL entities into efficient summaries")
public class OrderGatewayController {

    private final GraphQLUpstreamClient upstreamClient;

    public OrderGatewayController(GraphQLUpstreamClient upstreamClient) {
        this.upstreamClient = upstreamClient;
    }

    @GetMapping(value = "/{id}/summary", produces = MediaType.APPLICATION_JSON_VALUE)
    @Operation(
            summary = "Get order summary",
            description = "Fetches order summary by executing a field-optimized GraphQL query against the upstream service. Requests only required fields to eliminate over-fetching."
    )
    @ApiResponses(value = {
            @ApiResponse(
                    responseCode = "200",
                    description = "Order summary retrieved successfully with zero over-fetching",
                    content = @Content(mediaType = "application/json", schema = @Schema(implementation = OrderSummaryDTO.class))
            ),
            @ApiResponse(
                    responseCode = "404",
                    description = "Order not found upstream",
                    content = @Content(mediaType = "application/json", schema = @Schema(implementation = ProblemDetail.class))
            ),
            @ApiResponse(
                    responseCode = "502",
                    description = "Upstream GraphQL partial error or syntax fault translated to RFC 7807 problem details",
                    content = @Content(mediaType = "application/json", schema = @Schema(implementation = ProblemDetail.class))
            ),
            @ApiResponse(
                    responseCode = "504",
                    description = "Upstream GraphQL service timed out",
                    content = @Content(mediaType = "application/json", schema = @Schema(implementation = ProblemDetail.class))
            )
    })
    public ResponseEntity<OrderSummaryDTO> getOrderSummary(
            @Parameter(description = "Unique alphanumeric identifier of the order", example = "ORD-1001", required = true)
            @PathVariable("id") String id) {
        OrderSummaryDTO summary = upstreamClient.fetchOrderSummary(id);
        return ResponseEntity.ok(summary);
    }
}
