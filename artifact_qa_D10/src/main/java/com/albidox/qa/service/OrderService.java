package com.albidox.qa.service;

import com.albidox.qa.dto.CreateOrderRequest;
import com.albidox.qa.dto.OrderItemRequest;
import com.albidox.qa.dto.OrderItemResponse;
import com.albidox.qa.dto.OrderResponse;
import com.albidox.qa.exception.InsufficientStockException;
import com.albidox.qa.exception.InvalidOrderStateException;
import com.albidox.qa.exception.ResourceNotFoundException;
import com.albidox.qa.model.Customer;
import com.albidox.qa.model.Order;
import com.albidox.qa.model.OrderItem;
import com.albidox.qa.model.Product;
import com.albidox.qa.repository.AuditLogRepository;
import com.albidox.qa.repository.CustomerRepository;
import com.albidox.qa.repository.OrderRepository;
import com.albidox.qa.repository.ProductRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

@Service
public class OrderService {

    private final OrderRepository orderRepository;
    private final CustomerRepository customerRepository;
    private final ProductRepository productRepository;
    private final AuditLogRepository auditLogRepository;

    public OrderService(OrderRepository orderRepository,
                        CustomerRepository customerRepository,
                        ProductRepository productRepository,
                        AuditLogRepository auditLogRepository) {
        this.orderRepository = orderRepository;
        this.customerRepository = customerRepository;
        this.productRepository = productRepository;
        this.auditLogRepository = auditLogRepository;
    }

    @Transactional
    public OrderResponse createOrder(CreateOrderRequest request) {
        Customer customer = customerRepository.findById(request.customerId())
                .orElseThrow(() -> new ResourceNotFoundException("Customer not found with id: " + request.customerId()));

        BigDecimal totalAmount = BigDecimal.ZERO;
        List<ItemComputation> computations = new ArrayList<>();

        for (OrderItemRequest itemReq : request.items()) {
            Product product = productRepository.findById(itemReq.productId())
                    .orElseThrow(() -> new ResourceNotFoundException("Product not found with id: " + itemReq.productId()));

            boolean deducted = productRepository.deductStock(product.id(), itemReq.quantity());
            if (!deducted) {
                throw new InsufficientStockException("Insufficient stock for product " + product.name() + " (requested: " + itemReq.quantity() + ", available: " + product.stockQuantity() + ")");
            }

            BigDecimal subtotal = product.price().multiply(BigDecimal.valueOf(itemReq.quantity()));
            totalAmount = totalAmount.add(subtotal);
            computations.add(new ItemComputation(product, itemReq.quantity(), subtotal));
        }

        Order order = orderRepository.saveOrder(customer.id(), "PENDING", totalAmount);

        List<OrderItemResponse> itemResponses = new ArrayList<>();
        for (ItemComputation comp : computations) {
            OrderItem savedItem = orderRepository.saveOrderItem(
                    order.id(),
                    comp.product().id(),
                    comp.quantity(),
                    comp.product().price(),
                    comp.subtotal()
            );
            itemResponses.add(new OrderItemResponse(
                    savedItem.id(),
                    comp.product().id(),
                    comp.product().name(),
                    comp.quantity(),
                    comp.product().price(),
                    comp.subtotal()
            ));
        }

        auditLogRepository.log("ORDER", order.id(), "CREATE", "Order created with total: " + totalAmount);

        return new OrderResponse(
                order.id(),
                customer.id(),
                customer.name(),
                customer.email(),
                order.status(),
                order.totalAmount(),
                itemResponses,
                order.createdAt(),
                order.updatedAt()
        );
    }

    public OrderResponse getOrder(Long id) {
        Order order = orderRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found with id: " + id));

        Customer customer = customerRepository.findById(order.customerId())
                .orElseThrow(() -> new ResourceNotFoundException("Customer not found with id: " + order.customerId()));

        List<OrderItem> items = orderRepository.findItemsByOrderId(order.id());
        List<OrderItemResponse> itemResponses = new ArrayList<>();
        for (OrderItem item : items) {
            Product product = productRepository.findById(item.productId()).orElse(null);
            String productName = product != null ? product.name() : "Unknown Product";
            itemResponses.add(new OrderItemResponse(
                    item.id(),
                    item.productId(),
                    productName,
                    item.quantity(),
                    item.unitPrice(),
                    item.subtotal()
            ));
        }

        return new OrderResponse(
                order.id(),
                customer.id(),
                customer.name(),
                customer.email(),
                order.status(),
                order.totalAmount(),
                itemResponses,
                order.createdAt(),
                order.updatedAt()
        );
    }

    public List<OrderResponse> listOrders(Long customerId, String status, int limit, int offset) {
        List<Order> orders = orderRepository.findByCriteria(customerId, status, limit, offset);
        List<OrderResponse> responses = new ArrayList<>();
        for (Order order : orders) {
            responses.add(getOrder(order.id()));
        }
        return responses;
    }

    @Transactional
    public OrderResponse cancelOrder(Long id) {
        Order order = orderRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found with id: " + id));

        if ("CANCELLED".equalsIgnoreCase(order.status())) {
            throw new InvalidOrderStateException("Order is already cancelled: " + id);
        }
        if ("DELIVERED".equalsIgnoreCase(order.status())) {
            throw new InvalidOrderStateException("Cannot cancel an order that is already delivered: " + id);
        }

        List<OrderItem> items = orderRepository.findItemsByOrderId(order.id());
        for (OrderItem item : items) {
            productRepository.restoreStock(item.productId(), item.quantity());
        }

        orderRepository.updateStatus(order.id(), "CANCELLED");
        auditLogRepository.log("ORDER", order.id(), "CANCEL", "Order cancelled and stock restored");

        return getOrder(order.id());
    }

    private record ItemComputation(Product product, int quantity, BigDecimal subtotal) {}
}
