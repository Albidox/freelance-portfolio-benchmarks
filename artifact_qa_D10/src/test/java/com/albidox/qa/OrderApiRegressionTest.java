package com.albidox.qa;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;

import java.math.BigDecimal;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class OrderApiRegressionTest extends AbstractIntegrationTest {

    @Autowired
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        cleanTables();
    }

    @Test
    @DisplayName("Should create valid single item order returning HTTP 201 with contract payload")
    void shouldCreateValidSingleItemOrderWithHttp201() throws Exception {
        Long customerId = insertCustomer("Alice Smith", "alice@example.com");
        Long productId = insertProduct("SKU-ORD-1", "Mechanical Keyboard", new BigDecimal("120.00"), 50);

        Map<String, Object> payload = Map.of(
                "customerId", customerId,
                "items", List.of(
                        Map.of("productId", productId, "quantity", 2)
                )
        );

        mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id", notNullValue()))
                .andExpect(jsonPath("$.customerId", is(customerId.intValue())))
                .andExpect(jsonPath("$.customerName", is("Alice Smith")))
                .andExpect(jsonPath("$.customerEmail", is("alice@example.com")))
                .andExpect(jsonPath("$.status", is("PENDING")))
                .andExpect(jsonPath("$.totalAmount", is(240.00)))
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].productName", is("Mechanical Keyboard")))
                .andExpect(jsonPath("$.items[0].quantity", is(2)))
                .andExpect(jsonPath("$.items[0].subtotal", is(240.00)));
    }

    @Test
    @DisplayName("Should create order with multiple items and calculate accurate total amount")
    void shouldCreateValidMultipleItemsOrderAndCalculateAccurateTotal() throws Exception {
        Long customerId = insertCustomer("Bob Stone", "bob@example.com");
        Long prod1 = insertProduct("SKU-ORD-2", "USB-C Cable", new BigDecimal("15.50"), 20);
        Long prod2 = insertProduct("SKU-ORD-3", "Monitor Arm", new BigDecimal("80.00"), 10);

        Map<String, Object> payload = Map.of(
                "customerId", customerId,
                "items", List.of(
                        Map.of("productId", prod1, "quantity", 3), // 46.50
                        Map.of("productId", prod2, "quantity", 1)  // 80.00
                )
        );

        mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.totalAmount", is(126.50)))
                .andExpect(jsonPath("$.items", hasSize(2)));
    }

    @Test
    @DisplayName("Should deduct inventory atomically upon order creation")
    void shouldDeductInventoryAtomicallyOnOrderCreation() throws Exception {
        Long customerId = insertCustomer("Charlie Brown", "charlie@example.com");
        Long productId = insertProduct("SKU-ORD-4", "Ergonomic Mouse", new BigDecimal("65.00"), 30);

        Map<String, Object> payload = Map.of(
                "customerId", customerId,
                "items", List.of(Map.of("productId", productId, "quantity", 5))
        );

        mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isCreated());

        Integer remainingStock = jdbcTemplate.queryForObject(
                "SELECT stock_quantity FROM " + TEST_SCHEMA + ".products WHERE id = ?",
                Integer.class, productId);
        assertThat(remainingStock).isEqualTo(25);
    }

    @Test
    @DisplayName("Should reject order with null customer ID returning HTTP 400 Problem Detail")
    void shouldRejectOrderWithNullCustomerIdReturningHttp400ProblemDetail() throws Exception {
        Long productId = insertProduct("SKU-ORD-5", "Desk Mat", new BigDecimal("20.00"), 10);

        Map<String, Object> payload = Collections.singletonMap(
                "items", List.of(Map.of("productId", productId, "quantity", 1))
        );

        mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title", is("Validation Failed")))
                .andExpect(jsonPath("$.errors.customerId", notNullValue()));
    }

    @Test
    @DisplayName("Should reject order with non-existent customer returning HTTP 404 Problem Detail")
    void shouldRejectOrderWithNonExistentCustomerIdReturningHttp404() throws Exception {
        Long productId = insertProduct("SKU-ORD-6", "Laptop Stand", new BigDecimal("45.00"), 10);

        Map<String, Object> payload = Map.of(
                "customerId", 999999L,
                "items", List.of(Map.of("productId", productId, "quantity", 1))
        );

        mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title", is("Resource Not Found")));
    }

    @Test
    @DisplayName("Should reject order with empty items list returning HTTP 400 Problem Detail")
    void shouldRejectOrderWithEmptyItemsListReturningHttp400() throws Exception {
        Long customerId = insertCustomer("David White", "david@example.com");

        Map<String, Object> payload = Map.of(
                "customerId", customerId,
                "items", Collections.emptyList()
        );

        mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title", is("Validation Failed")));
    }

    @Test
    @DisplayName("Should reject order item with zero quantity returning HTTP 400 Problem Detail")
    void shouldRejectOrderWithZeroQuantityReturningHttp400() throws Exception {
        Long customerId = insertCustomer("Eva Green", "eva@example.com");
        Long productId = insertProduct("SKU-ORD-7", "Webcam 4K", new BigDecimal("150.00"), 10);

        Map<String, Object> payload = Map.of(
                "customerId", customerId,
                "items", List.of(Map.of("productId", productId, "quantity", 0))
        );

        mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title", is("Validation Failed")));
    }

    @Test
    @DisplayName("Should reject order item with negative quantity returning HTTP 400 Problem Detail")
    void shouldRejectOrderWithNegativeQuantityReturningHttp400() throws Exception {
        Long customerId = insertCustomer("Frank Black", "frank@example.com");
        Long productId = insertProduct("SKU-ORD-8", "Noise Cancelling Headphones", new BigDecimal("200.00"), 10);

        Map<String, Object> payload = Map.of(
                "customerId", customerId,
                "items", List.of(Map.of("productId", productId, "quantity", -3))
        );

        mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title", is("Validation Failed")));
    }

    @Test
    @DisplayName("Should reject order item with null product ID returning HTTP 400 Problem Detail")
    void shouldRejectOrderWithNullProductIdReturningHttp400() throws Exception {
        Long customerId = insertCustomer("Grace Hopper", "grace@example.com");

        Map<String, Object> payload = Collections.singletonMap(
                "customerId", customerId
        );

        mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("Should reject order with non-existent product ID returning HTTP 404 Problem Detail")
    void shouldRejectOrderWithNonExistentProductIdReturningHttp404() throws Exception {
        Long customerId = insertCustomer("Helen Keller", "helen@example.com");

        Map<String, Object> payload = Map.of(
                "customerId", customerId,
                "items", List.of(Map.of("productId", 999999L, "quantity", 1))
        );

        mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title", is("Resource Not Found")));
    }

    @Test
    @DisplayName("Should reject order when requested quantity exceeds available inventory returning HTTP 409")
    void shouldRejectOrderWhenRequestedQuantityExceedsAvailableStockReturningHttp409() throws Exception {
        Long customerId = insertCustomer("Ian Fleming", "ian@example.com");
        Long productId = insertProduct("SKU-ORD-9", "GPU RTX 4090", new BigDecimal("1600.00"), 2);

        Map<String, Object> payload = Map.of(
                "customerId", customerId,
                "items", List.of(Map.of("productId", productId, "quantity", 5))
        );

        mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title", is("Insufficient Stock")));

        Integer currentStock = jdbcTemplate.queryForObject(
                "SELECT stock_quantity FROM " + TEST_SCHEMA + ".products WHERE id = ?",
                Integer.class, productId);
        assertThat(currentStock).isEqualTo(2);
    }

    @Test
    @DisplayName("Should rollback inventory deduction completely when subsequent item in batch fails")
    void shouldRollbackStockDeductionWhenSubsequentItemFails() throws Exception {
        Long customerId = insertCustomer("Julia Child", "julia@example.com");
        Long prod1 = insertProduct("SKU-ORD-10", "Espresso Machine", new BigDecimal("500.00"), 5);
        Long prod2 = insertProduct("SKU-ORD-11", "Coffee Beans 1kg", new BigDecimal("25.00"), 1);

        // First item requests 2 (valid), second item requests 10 (exceeds stock of 1)
        Map<String, Object> payload = Map.of(
                "customerId", customerId,
                "items", List.of(
                        Map.of("productId", prod1, "quantity", 2),
                        Map.of("productId", prod2, "quantity", 10)
                )
        );

        mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title", is("Insufficient Stock")));

        // Verify prod1 inventory was rolled back to original 5
        Integer prod1Stock = jdbcTemplate.queryForObject(
                "SELECT stock_quantity FROM " + TEST_SCHEMA + ".products WHERE id = ?",
                Integer.class, prod1);
        assertThat(prod1Stock).isEqualTo(5);

        // Verify zero orders were committed
        Integer orderCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM " + TEST_SCHEMA + ".orders",
                Integer.class);
        assertThat(orderCount).isEqualTo(0);
    }

    @Test
    @DisplayName("Should fetch existing order by ID returning HTTP 200 with full hierarchy")
    void shouldGetExistingOrderByIdReturningHttp200WithFullHierarchy() throws Exception {
        Long customerId = insertCustomer("Kevin Flynn", "kevin@example.com");
        Long productId = insertProduct("SKU-ORD-12", "Virtual Identity Disk", new BigDecimal("99.99"), 10);

        Map<String, Object> payload = Map.of(
                "customerId", customerId,
                "items", List.of(Map.of("productId", productId, "quantity", 1))
        );

        String createResponse = mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();

        Long orderId = objectMapper.readTree(createResponse).get("id").asLong();

        mockMvc.perform(get("/api/v1/orders/" + orderId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id", is(orderId.intValue())))
                .andExpect(jsonPath("$.customerId", is(customerId.intValue())))
                .andExpect(jsonPath("$.customerName", is("Kevin Flynn")))
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].productName", is("Virtual Identity Disk")));
    }

    @Test
    @DisplayName("Should return HTTP 404 when getting non-existent order by ID")
    void shouldReturnHttp404WhenGettingNonExistentOrder() throws Exception {
        mockMvc.perform(get("/api/v1/orders/999999"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title", is("Resource Not Found")));
    }

    @Test
    @DisplayName("Should list orders with pagination parameters")
    void shouldListOrdersWithPagination() throws Exception {
        Long customerId = insertCustomer("Laura Croft", "laura@example.com");
        Long productId = insertProduct("SKU-ORD-13", "Compass", new BigDecimal("15.00"), 100);

        for (int i = 0; i < 5; i++) {
            Map<String, Object> payload = Map.of(
                    "customerId", customerId,
                    "items", List.of(Map.of("productId", productId, "quantity", 1))
            );
            mockMvc.perform(post("/api/v1/orders")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(payload)))
                    .andExpect(status().isCreated());
        }

        mockMvc.perform(get("/api/v1/orders?limit=2&offset=1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(2)));
    }

    @Test
    @DisplayName("Should filter orders by order status")
    void shouldFilterOrdersByStatus() throws Exception {
        Long customerId = insertCustomer("Mario Bros", "mario@example.com");
        Long productId = insertProduct("SKU-ORD-14", "Super Mushroom", new BigDecimal("5.00"), 100);

        Map<String, Object> payload = Map.of(
                "customerId", customerId,
                "items", List.of(Map.of("productId", productId, "quantity", 1))
        );
        String res = mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(payload)))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();

        Long orderId = objectMapper.readTree(res).get("id").asLong();

        // One order is PENDING, filter by PENDING
        mockMvc.perform(get("/api/v1/orders?status=PENDING"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].id", is(orderId.intValue())));

        // Filter by SHIPPED returns 0
        mockMvc.perform(get("/api/v1/orders?status=SHIPPED"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(0)));
    }

    @Test
    @DisplayName("Should filter orders by customer ID")
    void shouldFilterOrdersByCustomerId() throws Exception {
        Long c1 = insertCustomer("Neo Anderson", "neo@example.com");
        Long c2 = insertCustomer("Morpheus", "morpheus@example.com");
        Long prod = insertProduct("SKU-ORD-15", "Red Pill", new BigDecimal("1.00"), 50);

        mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("customerId", c1, "items", List.of(Map.of("productId", prod, "quantity", 1))))))
                .andExpect(status().isCreated());

        mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("customerId", c2, "items", List.of(Map.of("productId", prod, "quantity", 2))))))
                .andExpect(status().isCreated());

        mockMvc.perform(get("/api/v1/orders?customerId=" + c1))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].customerId", is(c1.intValue())));
    }

    @Test
    @DisplayName("Should cancel pending order and restore inventory automatically")
    void shouldCancelPendingOrderAndRestoreInventory() throws Exception {
        Long customerId = insertCustomer("Oliver Queen", "oliver@example.com");
        Long productId = insertProduct("SKU-ORD-16", "Compound Bow", new BigDecimal("350.00"), 10);

        String res = mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of(
                                "customerId", customerId,
                                "items", List.of(Map.of("productId", productId, "quantity", 3))
                        ))))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();

        Long orderId = objectMapper.readTree(res).get("id").asLong();

        // Inventory is 7
        Integer stockBeforeCancel = jdbcTemplate.queryForObject(
                "SELECT stock_quantity FROM " + TEST_SCHEMA + ".products WHERE id = ?",
                Integer.class, productId);
        assertThat(stockBeforeCancel).isEqualTo(7);

        // Cancel order
        mockMvc.perform(post("/api/v1/orders/" + orderId + "/cancel"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status", is("CANCELLED")));

        // Inventory restored to 10
        Integer stockAfterCancel = jdbcTemplate.queryForObject(
                "SELECT stock_quantity FROM " + TEST_SCHEMA + ".products WHERE id = ?",
                Integer.class, productId);
        assertThat(stockAfterCancel).isEqualTo(10);
    }

    @Test
    @DisplayName("Should reject cancellation of already cancelled order returning HTTP 409 Conflict")
    void shouldRejectCancellationOfAlreadyCancelledOrderReturningHttp409() throws Exception {
        Long customerId = insertCustomer("Peter Parker", "peter@example.com");
        Long productId = insertProduct("SKU-ORD-17", "Web Shooter", new BigDecimal("75.00"), 10);

        String res = mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of(
                                "customerId", customerId,
                                "items", List.of(Map.of("productId", productId, "quantity", 1))
                        ))))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();

        Long orderId = objectMapper.readTree(res).get("id").asLong();

        // First cancel succeeds
        mockMvc.perform(post("/api/v1/orders/" + orderId + "/cancel"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status", is("CANCELLED")));

        // Second cancel fails
        mockMvc.perform(post("/api/v1/orders/" + orderId + "/cancel"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title", is("Invalid Order State")));
    }

    @Test
    @DisplayName("Should reject cancellation of delivered order returning HTTP 409 Conflict")
    void shouldRejectCancellationOfDeliveredOrderReturningHttp409() throws Exception {
        Long customerId = insertCustomer("Quinn Fabray", "quinn@example.com");
        Long productId = insertProduct("SKU-ORD-18", "Cheer Uniform", new BigDecimal("60.00"), 10);

        String res = mockMvc.perform(post("/api/v1/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of(
                                "customerId", customerId,
                                "items", List.of(Map.of("productId", productId, "quantity", 1))
                        ))))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();

        Long orderId = objectMapper.readTree(res).get("id").asLong();

        // Transition order status directly to DELIVERED
        jdbcTemplate.update("UPDATE " + TEST_SCHEMA + ".orders SET status = 'DELIVERED' WHERE id = ?", orderId);

        // Attempt cancel fails
        mockMvc.perform(post("/api/v1/orders/" + orderId + "/cancel"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title", is("Invalid Order State")));
    }

    private Long insertCustomer(String name, String email) {
        String sql = "INSERT INTO " + TEST_SCHEMA + ".customers (name, email) VALUES (?, ?) RETURNING id";
        return jdbcTemplate.queryForObject(sql, Long.class, name, email);
    }

    private Long insertProduct(String sku, String name, BigDecimal price, int stock) {
        String sql = "INSERT INTO " + TEST_SCHEMA + ".products (sku, name, price, stock_quantity) VALUES (?, ?, ?, ?) RETURNING id";
        return jdbcTemplate.queryForObject(sql, Long.class, sku, name, price, stock);
    }
}
