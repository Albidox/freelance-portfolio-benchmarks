package com.albidox.qa.repository;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class AuditLogRepository {

    private final JdbcTemplate jdbcTemplate;

    public AuditLogRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public void log(String entityType, Long entityId, String action, String details) {
        String sql = "INSERT INTO audit_logs (entity_type, entity_id, action, details) VALUES (?, ?, ?, ?)";
        jdbcTemplate.update(sql, entityType, entityId, action, details);
    }
}
