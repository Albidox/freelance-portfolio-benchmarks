package com.albidox.qa.repository;

import com.albidox.qa.model.Order;
import com.albidox.qa.model.OrderItem;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

@Repository
public class OrderRepository {

    private final JdbcTemplate jdbcTemplate;

    public OrderRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    private final RowMapper<Order> orderRowMapper = (rs, rowNum) -> new Order(
            rs.getLong("id"),
            rs.getLong("customer_id"),
            rs.getString("status"),
            rs.getBigDecimal("total_amount"),
            rs.getObject("created_at", OffsetDateTime.class),
            rs.getObject("updated_at", OffsetDateTime.class)
    );

    private final RowMapper<OrderItem> itemRowMapper = (rs, rowNum) -> new OrderItem(
            rs.getLong("id"),
            rs.getLong("order_id"),
            rs.getLong("product_id"),
            rs.getInt("quantity"),
            rs.getBigDecimal("unit_price"),
            rs.getBigDecimal("subtotal")
    );

    public Order saveOrder(Long customerId, String status, BigDecimal totalAmount) {
        String sql = "INSERT INTO orders (customer_id, status, total_amount) VALUES (?, ?, ?) RETURNING id, customer_id, status, total_amount, created_at, updated_at";
        return jdbcTemplate.queryForObject(sql, orderRowMapper, customerId, status, totalAmount);
    }

    public OrderItem saveOrderItem(Long orderId, Long productId, int quantity, BigDecimal unitPrice, BigDecimal subtotal) {
        String sql = "INSERT INTO order_items (order_id, product_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?) RETURNING id, order_id, product_id, quantity, unit_price, subtotal";
        return jdbcTemplate.queryForObject(sql, itemRowMapper, orderId, productId, quantity, unitPrice, subtotal);
    }

    public Optional<Order> findById(Long id) {
        String sql = "SELECT id, customer_id, status, total_amount, created_at, updated_at FROM orders WHERE id = ?";
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject(sql, orderRowMapper, id));
        } catch (EmptyResultDataAccessException e) {
            return Optional.empty();
        }
    }

    public List<OrderItem> findItemsByOrderId(Long orderId) {
        String sql = "SELECT id, order_id, product_id, quantity, unit_price, subtotal FROM order_items WHERE order_id = ? ORDER BY id";
        return jdbcTemplate.query(sql, itemRowMapper, orderId);
    }

    public List<Order> findByCriteria(Long customerId, String status, int limit, int offset) {
        StringBuilder sql = new StringBuilder("SELECT id, customer_id, status, total_amount, created_at, updated_at FROM orders WHERE 1=1");
        List<Object> params = new ArrayList<>();

        if (customerId != null) {
            sql.append(" AND customer_id = ?");
            params.add(customerId);
        }
        if (status != null && !status.isBlank()) {
            sql.append(" AND status = ?");
            params.add(status);
        }

        sql.append(" ORDER BY id DESC LIMIT ? OFFSET ?");
        params.add(limit);
        params.add(offset);

        return jdbcTemplate.query(sql.toString(), orderRowMapper, params.toArray());
    }

    public void updateStatus(Long orderId, String newStatus) {
        String sql = "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?";
        jdbcTemplate.update(sql, newStatus, orderId);
    }
}
