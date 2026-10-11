package com.albidox.qa.repository;

import com.albidox.qa.model.Product;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;

@Repository
public class ProductRepository {

    private final JdbcTemplate jdbcTemplate;

    public ProductRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    private final RowMapper<Product> rowMapper = (rs, rowNum) -> new Product(
            rs.getLong("id"),
            rs.getString("sku"),
            rs.getString("name"),
            rs.getBigDecimal("price"),
            rs.getInt("stock_quantity"),
            rs.getObject("created_at", OffsetDateTime.class)
    );

    public Product save(String sku, String name, BigDecimal price, int stockQuantity) {
        String sql = "INSERT INTO products (sku, name, price, stock_quantity) VALUES (?, ?, ?, ?) RETURNING id, sku, name, price, stock_quantity, created_at";
        return jdbcTemplate.queryForObject(sql, rowMapper, sku, name, price, stockQuantity);
    }

    public Optional<Product> findById(Long id) {
        String sql = "SELECT id, sku, name, price, stock_quantity, created_at FROM products WHERE id = ?";
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject(sql, rowMapper, id));
        } catch (EmptyResultDataAccessException e) {
            return Optional.empty();
        }
    }

    public Optional<Product> findBySku(String sku) {
        String sql = "SELECT id, sku, name, price, stock_quantity, created_at FROM products WHERE sku = ?";
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject(sql, rowMapper, sku));
        } catch (EmptyResultDataAccessException e) {
            return Optional.empty();
        }
    }

    public List<Product> findAll(int limit, int offset) {
        String sql = "SELECT id, sku, name, price, stock_quantity, created_at FROM products ORDER BY id LIMIT ? OFFSET ?";
        return jdbcTemplate.query(sql, rowMapper, limit, offset);
    }

    public boolean deductStock(Long productId, int quantity) {
        String sql = "UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ? AND stock_quantity >= ?";
        int updatedRows = jdbcTemplate.update(sql, quantity, productId, quantity);
        return updatedRows > 0;
    }

    public void restoreStock(Long productId, int quantity) {
        String sql = "UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?";
        jdbcTemplate.update(sql, quantity, productId);
    }
}
