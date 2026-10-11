package com.ashfaq.migration;

import com.ashfaq.migration.model.AuditLog;
import com.ashfaq.migration.model.Customer;
import com.ashfaq.migration.model.Invoice;
import com.ashfaq.migration.model.OrderEntity;
import com.ashfaq.migration.model.Product;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;

import java.math.BigDecimal;
import java.util.Date;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
public class EntityCompilationTest {

    @Autowired
    private TestEntityManager entityManager;

    @Test
    @DisplayName("Verified: Jakarta persistence entities persist cleanly to H2 database")
    void testJakartaEntitiesPersistSuccessfully() {
        // 1. Verify Customer
        Customer customer = new Customer("Sk Ashfaq Bux", "ashfaq@example.com");
        Customer savedCustomer = entityManager.persistAndFlush(customer);
        assertThat(savedCustomer.getId()).isNotNull();
        assertThat(savedCustomer.getName()).isEqualTo("Sk Ashfaq Bux");
        assertThat(savedCustomer.getEmail()).isEqualTo("ashfaq@example.com");

        // 2. Verify Product
        Product product = new Product("SKU-9901", "Enterprise Modernization Suite", new BigDecimal("1299.99"));
        Product savedProduct = entityManager.persistAndFlush(product);
        assertThat(savedProduct.getId()).isNotNull();
        assertThat(savedProduct.getSku()).isEqualTo("SKU-9901");
        assertThat(savedProduct.getPrice()).isEqualByComparingTo(new BigDecimal("1299.99"));

        // 3. Verify OrderEntity & Invoice
        OrderEntity order = new OrderEntity("ORD-2026-001", OrderEntity.OrderStatus.CONFIRMED, savedCustomer);
        Invoice invoice = new Invoice(order, new BigDecimal("1299.99"), new Date());
        order.addInvoice(invoice);

        OrderEntity savedOrder = entityManager.persistAndFlush(order);
        assertThat(savedOrder.getId()).isNotNull();
        assertThat(savedOrder.getOrderNumber()).isEqualTo("ORD-2026-001");
        assertThat(savedOrder.getInvoices()).hasSize(1);
        assertThat(savedOrder.getInvoices().get(0).getId()).isNotNull();

        // 4. Verify AuditLog with Lifecycle callbacks
        AuditLog auditLog = new AuditLog("Customer", "MIGRATE_JAKARTA_AST");
        AuditLog savedAudit = entityManager.persistAndFlush(auditLog);
        assertThat(savedAudit.getId()).isNotNull();
        assertThat(savedAudit.getCreatedAt()).isNotNull();
        assertThat(savedAudit.getAction()).isEqualTo("MIGRATE_JAKARTA_AST");
    }
}
