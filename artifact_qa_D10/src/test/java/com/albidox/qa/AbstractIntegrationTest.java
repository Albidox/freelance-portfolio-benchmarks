package com.albidox.qa;

import org.flywaydb.core.Flyway;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.sql.Statement;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK)
@AutoConfigureMockMvc
public abstract class AbstractIntegrationTest {

    protected static final String TEST_SCHEMA = "d10_regression_sandbox";
    protected static final String DB_URL = "jdbc:postgresql://127.0.0.1:5433/artifact_d10_db?currentSchema=" + TEST_SCHEMA;
    protected static final String DB_USER = "postgres";
    protected static final String DB_PASSWORD = "";

    @Autowired
    protected MockMvc mockMvc;

    @Autowired
    protected JdbcTemplate jdbcTemplate;

    @Autowired
    protected Flyway flyway;

    @DynamicPropertySource
    static void configureDatasource(DynamicPropertyRegistry registry) {
        ensureSchemaExists();
        registry.add("spring.datasource.url", () -> DB_URL);
        registry.add("spring.datasource.username", () -> DB_USER);
        registry.add("spring.datasource.password", () -> DB_PASSWORD);
        registry.add("spring.datasource.driver-class-name", () -> "org.postgresql.Driver");
        registry.add("spring.flyway.schemas", () -> TEST_SCHEMA);
        registry.add("spring.flyway.default-schema", () -> TEST_SCHEMA);
        registry.add("spring.flyway.create-schemas", () -> "true");
    }

    private static void ensureSchemaExists() {
        try (Connection conn = DriverManager.getConnection("jdbc:postgresql://127.0.0.1:5433/artifact_d10_db", DB_USER, DB_PASSWORD);
             Statement stmt = conn.createStatement()) {
            stmt.execute("CREATE SCHEMA IF NOT EXISTS " + TEST_SCHEMA);
        } catch (SQLException e) {
            throw new RuntimeException("Failed to ensure PostgreSQL test schema exists: " + e.getMessage(), e);
        }
    }

    protected void cleanTables() {
        jdbcTemplate.execute("DELETE FROM " + TEST_SCHEMA + ".audit_logs");
        jdbcTemplate.execute("DELETE FROM " + TEST_SCHEMA + ".order_items");
        jdbcTemplate.execute("DELETE FROM " + TEST_SCHEMA + ".orders");
        jdbcTemplate.execute("DELETE FROM " + TEST_SCHEMA + ".products");
        jdbcTemplate.execute("DELETE FROM " + TEST_SCHEMA + ".customers");
    }
}
