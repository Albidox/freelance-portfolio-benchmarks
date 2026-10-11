package com.ashfaq.migration.model;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;
import jakarta.persistence.Id;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Column;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.annotation.PostConstruct;
import java.time.Instant;

@Entity
@Table(name = "audit_logs")
public class AuditLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "entity_name", nullable = false)
    private String entityName;

    @Column(name = "action", nullable = false)
    private String action;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    public AuditLog() {
    }

    public AuditLog(String entityName, String action) {
        this.entityName = entityName;
        this.action = action;
    }

    @PostConstruct
    public void init() {
        // Initialization verification callback
    }

    @PrePersist
    protected void onPrePersist() {
        this.createdAt = Instant.now();
    }

    @PreUpdate
    protected void onPreUpdate() {
        this.createdAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getEntityName() {
        return entityName;
    }

    public void setEntityName(String entityName) {
        this.entityName = entityName;
    }

    public String getAction() {
        return action;
    }

    public void setAction(String action) {
        this.action = action;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }
}
