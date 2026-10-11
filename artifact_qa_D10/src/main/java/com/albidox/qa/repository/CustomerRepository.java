package com.albidox.qa.repository;

import com.albidox.qa.model.Customer;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;

@Repository
public class CustomerRepository {

    private final JdbcTemplate jdbcTemplate;

    public CustomerRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    private final RowMapper<Customer> rowMapper = (rs, rowNum) -> new Customer(
            rs.getLong("id"),
            rs.getString("name"),
            rs.getString("email"),
            rs.getString("status"),
            rs.getObject("created_at", OffsetDateTime.class)
    );

    public Customer save(String name, String email) {
        String sql = "INSERT INTO customers (name, email) VALUES (?, ?) RETURNING id, name, email, status, created_at";
        return jdbcTemplate.queryForObject(sql, rowMapper, name, email);
    }

    public Optional<Customer> findById(Long id) {
        String sql = "SELECT id, name, email, status, created_at FROM customers WHERE id = ?";
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject(sql, rowMapper, id));
        } catch (EmptyResultDataAccessException e) {
            return Optional.empty();
        }
    }

    public Optional<Customer> findByEmail(String email) {
        String sql = "SELECT id, name, email, status, created_at FROM customers WHERE email = ?";
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject(sql, rowMapper, email));
        } catch (EmptyResultDataAccessException e) {
            return Optional.empty();
        }
    }

    public List<Customer> findAll(int limit, int offset) {
        String sql = "SELECT id, name, email, status, created_at FROM customers ORDER BY id LIMIT ? OFFSET ?";
        return jdbcTemplate.query(sql, rowMapper, limit, offset);
    }
}
