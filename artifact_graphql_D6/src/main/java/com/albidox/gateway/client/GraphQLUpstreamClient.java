package com.albidox.gateway.client;

import com.albidox.gateway.dto.GraphQLOrderResponse;
import com.albidox.gateway.dto.GraphQLRequest;
import com.albidox.gateway.dto.OrderSummaryDTO;
import com.albidox.gateway.exception.ResourceNotFoundException;
import com.albidox.gateway.exception.UpstreamGraphQLException;
import com.albidox.gateway.exception.UpstreamTimeoutException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.TimeoutException;

@Component
public class GraphQLUpstreamClient {

    private static final Logger log = LoggerFactory.getLogger(GraphQLUpstreamClient.class);

    // Exact parameterized GraphQL query requesting strictly the 5 fields needed by OrderSummaryDTO
    public static final String ORDER_SUMMARY_QUERY = """
            query GetOrderSummary($id: ID!) {
              order(id: $id) {
                id
                status
                totalAmount
                user {
                  name
                }
                lineItems {
                  id
                }
              }
            }
            """;

    private final WebClient webClient;
    private final long timeoutMs;

    public GraphQLUpstreamClient(
            WebClient webClient,
            @Value("${graphql.upstream.timeout-ms:1000}") long timeoutMs) {
        this.webClient = webClient;
        this.timeoutMs = timeoutMs;
    }

    public OrderSummaryDTO fetchOrderSummary(String orderId) {
        log.debug("Executing upstream GraphQL query for orderId: {}", orderId);

        GraphQLRequest requestBody = new GraphQLRequest(ORDER_SUMMARY_QUERY, Map.of("id", orderId));

        GraphQLOrderResponse response;
        try {
            response = webClient.post()
                    .bodyValue(requestBody)
                    .retrieve()
                    .bodyToMono(GraphQLOrderResponse.class)
                    .timeout(Duration.ofMillis(timeoutMs))
                    .block();
        } catch (Exception ex) {
            Throwable cause = ex.getCause() != null ? ex.getCause() : ex;
            if (ex instanceof TimeoutException || cause instanceof TimeoutException
                    || ex.getMessage() != null && ex.getMessage().toLowerCase().contains("timeout")) {
                log.warn("Upstream GraphQL timeout triggered for orderId: {}", orderId);
                throw new UpstreamTimeoutException(
                        "Upstream GraphQL service timed out after " + timeoutMs + "ms for order: " + orderId, ex);
            }
            if (ex instanceof WebClientRequestException) {
                log.error("Network failure connecting to upstream GraphQL: {}", ex.getMessage());
                throw new UpstreamTimeoutException("Network connectivity failure to upstream GraphQL service", ex);
            }
            throw ex;
        }

        if (response == null) {
            throw new UpstreamGraphQLException("Received null response from upstream GraphQL service", null);
        }

        // Validate error conditions: partial failures and entity absence
        if (response.errors() != null && !response.errors().isEmpty()) {
            boolean hasEntityNotFound = response.errors().stream()
                    .anyMatch(err -> err.extensions() != null && "ENTITY_NOT_FOUND".equals(err.extensions().get("code"))
                            || (err.message() != null && err.message().toLowerCase().contains("not found")));

            if (hasEntityNotFound && (response.data() == null || response.data().order() == null)) {
                log.info("Order '{}' not found upstream", orderId);
                throw new ResourceNotFoundException("Order with ID '" + orderId + "' was not found upstream");
            }

            log.warn("Upstream GraphQL returned errors for orderId {}: {}", orderId, response.errors());
            throw new UpstreamGraphQLException(
                    "Upstream GraphQL service reported execution errors for order: " + orderId,
                    response.errors());
        }

        if (response.data() == null || response.data().order() == null) {
            log.info("Order '{}' not found upstream (null order payload)", orderId);
            throw new ResourceNotFoundException("Order with ID '" + orderId + "' was not found upstream");
        }

        GraphQLOrderResponse.OrderNode order = response.data().order();

        String customerName = (order.user() != null) ? order.user().name() : "Unknown Customer";
        int lineItemCount = (order.lineItems() != null) ? order.lineItems().size() : 0;

        return new OrderSummaryDTO(
                order.id(),
                customerName,
                order.totalAmount(),
                order.status(),
                lineItemCount
        );
    }
}
