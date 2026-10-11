package com.albidox.gateway;

import com.albidox.gateway.client.GraphQLUpstreamClient;
import com.albidox.gateway.controller.OrderGatewayController;
import com.albidox.gateway.dto.GraphQLOrderResponse.GraphQLErrorDetail;
import com.albidox.gateway.dto.OrderSummaryDTO;
import com.albidox.gateway.exception.GlobalExceptionHandler;
import com.albidox.gateway.exception.ResourceNotFoundException;
import com.albidox.gateway.exception.UpstreamGraphQLException;
import com.albidox.gateway.exception.UpstreamTimeoutException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(OrderGatewayController.class)
@Import(GlobalExceptionHandler.class)
class OrderGatewayControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private GraphQLUpstreamClient upstreamClient;

    @Test
    @DisplayName("Should successfully return OrderSummaryDTO with 200 OK")
    void shouldReturnOrderSummarySuccessfully() throws Exception {
        OrderSummaryDTO mockSummary = new OrderSummaryDTO(
                "ORD-1001",
                "Alice Vance",
                new BigDecimal("249.99"),
                "CONFIRMED",
                3
        );

        when(upstreamClient.fetchOrderSummary("ORD-1001")).thenReturn(mockSummary);

        mockMvc.perform(get("/api/v1/orders/ORD-1001/summary")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.orderId").value("ORD-1001"))
                .andExpect(jsonPath("$.customerName").value("Alice Vance"))
                .andExpect(jsonPath("$.totalAmount").value(249.99))
                .andExpect(jsonPath("$.status").value("CONFIRMED"))
                .andExpect(jsonPath("$.lineItemCount").value(3));
    }

    @Test
    @DisplayName("Should return 404 RFC 7807 problem details when order not found")
    void shouldReturn404WhenOrderNotFound() throws Exception {
        when(upstreamClient.fetchOrderSummary("ORD-9999"))
                .thenThrow(new ResourceNotFoundException("Order with ID 'ORD-9999' was not found upstream"));

        mockMvc.perform(get("/api/v1/orders/ORD-9999/summary")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Resource Not Found"))
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.detail").value("Order with ID 'ORD-9999' was not found upstream"));
    }

    @Test
    @DisplayName("Should return 502 RFC 7807 problem details on upstream GraphQL errors")
    void shouldReturn502OnUpstreamGraphQLError() throws Exception {
        GraphQLErrorDetail errorDetail = new GraphQLErrorDetail(
                "User resolution failed",
                List.of("order", "user"),
                Map.of("code", "DOWNSTREAM_UNAVAILABLE")
        );
        when(upstreamClient.fetchOrderSummary("ORD-PARTIAL"))
                .thenThrow(new UpstreamGraphQLException("Upstream error occurred", List.of(errorDetail)));

        mockMvc.perform(get("/api/v1/orders/ORD-PARTIAL/summary")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.title").value("Upstream GraphQL Error"))
                .andExpect(jsonPath("$.status").value(502))
                .andExpect(jsonPath("$.upstreamErrors[0].message").value("User resolution failed"));
    }

    @Test
    @DisplayName("Should return 504 RFC 7807 problem details on upstream timeout")
    void shouldReturn504OnUpstreamTimeout() throws Exception {
        when(upstreamClient.fetchOrderSummary("ORD-TIMEOUT"))
                .thenThrow(new UpstreamTimeoutException("Upstream GraphQL service timed out after 1000ms"));

        mockMvc.perform(get("/api/v1/orders/ORD-TIMEOUT/summary")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isGatewayTimeout())
                .andExpect(jsonPath("$.title").value("Upstream Gateway Timeout"))
                .andExpect(jsonPath("$.status").value(504));
    }
}
