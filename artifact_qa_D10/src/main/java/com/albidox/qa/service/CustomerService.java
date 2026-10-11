package com.albidox.qa.service;

import com.albidox.qa.dto.CreateCustomerRequest;
import com.albidox.qa.exception.ResourceNotFoundException;
import com.albidox.qa.model.Customer;
import com.albidox.qa.repository.AuditLogRepository;
import com.albidox.qa.repository.CustomerRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class CustomerService {

    private final CustomerRepository customerRepository;
    private final AuditLogRepository auditLogRepository;

    public CustomerService(CustomerRepository customerRepository, AuditLogRepository auditLogRepository) {
        this.customerRepository = customerRepository;
        this.auditLogRepository = auditLogRepository;
    }

    @Transactional
    public Customer createCustomer(CreateCustomerRequest request) {
        customerRepository.findByEmail(request.email()).ifPresent(c -> {
            throw new IllegalArgumentException("Customer with email already exists: " + request.email());
        });
        Customer customer = customerRepository.save(request.name(), request.email());
        auditLogRepository.log("CUSTOMER", customer.id(), "CREATE", "Customer created: " + customer.email());
        return customer;
    }

    public Customer getCustomer(Long id) {
        return customerRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Customer not found with id: " + id));
    }

    public List<Customer> listCustomers(int limit, int offset) {
        return customerRepository.findAll(limit, offset);
    }
}
