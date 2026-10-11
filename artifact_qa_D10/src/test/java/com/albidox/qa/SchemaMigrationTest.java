package com.albidox.qa;

import org.flywaydb.core.api.MigrationInfo;
import org.flywaydb.core.api.MigrationState;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataIntegrityViolationException;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SchemaMigrationTest extends AbstractIntegrationTest {

    @BeforeEach
    void setUp() {
        cleanTables();
    }

    @Test
    @DisplayName("Assert Flyway migrations apply cleanly and reach SUCCESS state")
    void shouldApplyAllMigrationsCleanly() {
        MigrationInfo[] migrations = flyway.info().all();
        assertThat(migrations).isNotEmpty();
        for (MigrationInfo migration : migrations) {
            assertThat(migration.getState())
                    .as("Migration " + migration.getScript() + " state")
                    .isEqualTo(MigrationState.SUCCESS);
        }
    }

    @Test
    @DisplayName("Assert flyway_schema_history table exists in sandbox schema")
    void shouldVerifyFlywaySchemaHistoryTableExists() {
        String sql = "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = ? AND table_name = 'flyway_schema_history'";
        Integer count = jdbcTemplate.queryForObject(sql, Integer.class, TEST_SCHEMA);
        assertThat(count).isEqualTo(1);
    }

    @Test
    @DisplayName("Assert all applied migrations have non-zero CRC32 checksums")
    void shouldValidateMigrationChecksumsAreNonZero() {
        String sql = "SELECT checksum FROM " + TEST_SCHEMA + ".flyway_schema_history ORDER BY installed_rank";
        List<Integer> checksums = jdbcTemplate.queryForList(sql, Integer.class);
        assertThat(checksums).hasSizeGreaterThanOrEqualTo(2);
        for (Integer checksum : checksums) {
            assertThat(checksum).isNotNull().isNotZero();
        }
    }

    @Test
    @DisplayName("Assert customers table enforces email unique constraint")
    void shouldEnforceCustomersEmailUniqueConstraint() {
        String sql = "INSERT INTO " + TEST_SCHEMA + ".customers (name, email) VALUES (?, ?)";
        jdbcTemplate.update(sql, "Customer Alpha", "alpha@example.com");

        assertThatThrownBy(() -> jdbcTemplate.update(sql, "Customer Beta", "alpha@example.com"))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("Assert customers table enforces status check constraint")
    void shouldEnforceCustomersStatusCheckConstraint() {
        String sql = "INSERT INTO " + TEST_SCHEMA + ".customers (name, email, status) VALUES (?, ?, ?)";
        assertThatThrownBy(() -> jdbcTemplate.update(sql, "Customer Invalid", "invalid@example.com", "DISALLOWED_STATUS"))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("Assert products table rejects negative price via check constraint")
    void shouldEnforceProductsPriceNonNegativeCheckConstraint() {
        String sql = "INSERT INTO " + TEST_SCHEMA + ".products (sku, name, price, stock_quantity) VALUES (?, ?, ?, ?)";
        assertThatThrownBy(() -> jdbcTemplate.update(sql, "SKU-NEG-1", "Faulty Item", new BigDecimal("-10.00"), 5))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("Assert products table rejects negative stock quantity via check constraint")
    void shouldEnforceProductsStockQuantityNonNegativeCheckConstraint() {
        String sql = "INSERT INTO " + TEST_SCHEMA + ".products (sku, name, price, stock_quantity) VALUES (?, ?, ?, ?)";
        assertThatThrownBy(() -> jdbcTemplate.update(sql, "SKU-NEG-2", "Faulty Item", new BigDecimal("10.00"), -5))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("Assert orders table rejects invalid status string via check constraint")
    void shouldEnforceOrdersStatusCheckConstraint() {
        Long customerId = createSampleCustomer("Cust Check", "cust.check@example.com");
        String sql = "INSERT INTO " + TEST_SCHEMA + ".orders (customer_id, status, total_amount) VALUES (?, ?, ?)";
        assertThatThrownBy(() -> jdbcTemplate.update(sql, customerId, "BOGUS_STATUS", BigDecimal.ZERO))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("Assert order_items table rejects zero or negative quantity")
    void shouldEnforceOrderItemsQuantityPositiveCheckConstraint() {
        Long customerId = createSampleCustomer("Cust Item Check", "cust.item@example.com");
        Long orderId = createSampleOrder(customerId);
        Long productId = createSampleProduct("SKU-CHK-1", "Product Chk", new BigDecimal("25.00"), 10);

        String sql = "INSERT INTO " + TEST_SCHEMA + ".order_items (order_id, product_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)";
        assertThatThrownBy(() -> jdbcTemplate.update(sql, orderId, productId, 0, new BigDecimal("25.00"), BigDecimal.ZERO))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("Assert order_items table rejects negative unit price")
    void shouldEnforceOrderItemsUnitPriceNonNegativeCheckConstraint() {
        Long customerId = createSampleCustomer("Cust Price Check", "cust.price@example.com");
        Long orderId = createSampleOrder(customerId);
        Long productId = createSampleProduct("SKU-CHK-2", "Product Chk 2", new BigDecimal("25.00"), 10);

        String sql = "INSERT INTO " + TEST_SCHEMA + ".order_items (order_id, product_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)";
        assertThatThrownBy(() -> jdbcTemplate.update(sql, orderId, productId, 1, new BigDecimal("-5.00"), new BigDecimal("-5.00")))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("Assert orders table enforces foreign key constraint to customers")
    void shouldEnforceForeignKeyOrdersToCustomers() {
        String sql = "INSERT INTO " + TEST_SCHEMA + ".orders (customer_id, status, total_amount) VALUES (?, ?, ?)";
        assertThatThrownBy(() -> jdbcTemplate.update(sql, 999999L, "PENDING", BigDecimal.ZERO))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("Assert order_items table enforces foreign key constraint to orders")
    void shouldEnforceForeignKeyOrderItemsToOrders() {
        Long productId = createSampleProduct("SKU-CHK-3", "Product Chk 3", new BigDecimal("15.00"), 10);
        String sql = "INSERT INTO " + TEST_SCHEMA + ".order_items (order_id, product_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)";
        assertThatThrownBy(() -> jdbcTemplate.update(sql, 999999L, productId, 1, new BigDecimal("15.00"), new BigDecimal("15.00")))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("Assert order_items table enforces foreign key constraint to products")
    void shouldEnforceForeignKeyOrderItemsToProducts() {
        Long customerId = createSampleCustomer("Cust Prod FK", "cust.fk@example.com");
        Long orderId = createSampleOrder(customerId);

        String sql = "INSERT INTO " + TEST_SCHEMA + ".order_items (order_id, product_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)";
        assertThatThrownBy(() -> jdbcTemplate.update(sql, orderId, 999999L, 1, new BigDecimal("15.00"), new BigDecimal("15.00")))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("Assert foreign key indexes exist in PostgreSQL catalog to prevent lock contention")
    void shouldVerifyAllForeignKeyIndexesExistInPostgresCatalog() {
        String sql = "SELECT indexname FROM pg_indexes WHERE schemaname = ? AND tablename = ?";
        List<String> orderIndexes = jdbcTemplate.queryForList(sql, String.class, TEST_SCHEMA, "orders");
        assertThat(orderIndexes).contains("idx_orders_customer_id");

        List<String> orderItemIndexes = jdbcTemplate.queryForList(sql, String.class, TEST_SCHEMA, "order_items");
        assertThat(orderItemIndexes).contains("idx_order_items_order_id", "idx_order_items_product_id");
    }

    @Test
    @DisplayName("Assert audit_logs table and performance index exist in schema")
    void shouldVerifyAuditLogsTableAndIndexesExist() {
        String tableSql = "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = ? AND table_name = 'audit_logs'";
        Integer tableCount = jdbcTemplate.queryForObject(tableSql, Integer.class, TEST_SCHEMA);
        assertThat(tableCount).isEqualTo(1);

        String indexSql = "SELECT indexname FROM pg_indexes WHERE schemaname = ? AND tablename = 'audit_logs'";
        List<String> auditIndexes = jdbcTemplate.queryForList(indexSql, String.class, TEST_SCHEMA);
        assertThat(auditIndexes).contains("idx_audit_logs_entity", "idx_audit_logs_created_at");
    }

    private Long createSampleCustomer(String name, String email) {
        String sql = "INSERT INTO " + TEST_SCHEMA + ".customers (name, email) VALUES (?, ?) RETURNING id";
        return jdbcTemplate.queryForObject(sql, Long.class, name, email);
    }

    private Long createSampleProduct(String sku, String name, BigDecimal price, int stock) {
        String sql = "INSERT INTO " + TEST_SCHEMA + ".products (sku, name, price, stock_quantity) VALUES (?, ?, ?, ?) RETURNING id";
        return jdbcTemplate.queryForObject(sql, Long.class, sku, name, price, stock);
    }

    private Long createSampleOrder(Long customerId) {
        String sql = "INSERT INTO " + TEST_SCHEMA + ".orders (customer_id, status, total_amount) VALUES (?, 'PENDING', 0.00) RETURNING id";
        return jdbcTemplate.queryForObject(sql, Long.class, customerId);
    }
}
