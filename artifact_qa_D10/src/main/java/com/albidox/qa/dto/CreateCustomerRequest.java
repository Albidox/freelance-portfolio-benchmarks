package com.albidox.qa.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

public record CreateCustomerRequest(
        @NotBlank(message = "Customer name is required")
        String name,

        @NotBlank(message = "Customer email is required")
        @Email(message = "Invalid email format")
        String email
) {}
