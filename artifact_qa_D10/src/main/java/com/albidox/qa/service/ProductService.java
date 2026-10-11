package com.albidox.qa.service;

import com.albidox.qa.dto.CreateProductRequest;
import com.albidox.qa.exception.ResourceNotFoundException;
import com.albidox.qa.model.Product;
import com.albidox.qa.repository.AuditLogRepository;
import com.albidox.qa.repository.ProductRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class ProductService {

    private final ProductRepository productRepository;
    private final AuditLogRepository auditLogRepository;

    public ProductService(ProductRepository productRepository, AuditLogRepository auditLogRepository) {
        this.productRepository = productRepository;
        this.auditLogRepository = auditLogRepository;
    }

    @Transactional
    public Product createProduct(CreateProductRequest request) {
        productRepository.findBySku(request.sku()).ifPresent(p -> {
            throw new IllegalArgumentException("Product with SKU already exists: " + request.sku());
        });
        Product product = productRepository.save(request.sku(), request.name(), request.price(), request.stockQuantity());
        auditLogRepository.log("PRODUCT", product.id(), "CREATE", "Product created: " + product.sku());
        return product;
    }

    public Product getProduct(Long id) {
        return productRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Product not found with id: " + id));
    }

    public List<Product> listProducts(int limit, int offset) {
        return productRepository.findAll(limit, offset);
    }
}
