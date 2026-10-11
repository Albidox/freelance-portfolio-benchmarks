package com.albidox.security.controller;

import com.albidox.security.dto.ApiResponse;
import com.albidox.security.dto.LoginRequest;
import com.albidox.security.dto.LoginResponse;
import com.albidox.security.security.JwtTokenProvider;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private final JwtTokenProvider jwtTokenProvider;

    public AuthController(JwtTokenProvider jwtTokenProvider) {
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @PostMapping("/login")
    public ResponseEntity<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        List<String> roles = new ArrayList<>();

        if (request.role() != null && !request.role().isBlank()) {
            String formattedRole = request.role().toUpperCase();
            if (!formattedRole.startsWith("ROLE_")) {
                formattedRole = "ROLE_" + formattedRole;
            }
            roles.add(formattedRole);
        } else if ("admin".equalsIgnoreCase(request.username())) {
            roles.add("ROLE_ADMIN");
        } else if ("manager".equalsIgnoreCase(request.username())) {
            roles.add("ROLE_MANAGER");
        } else {
            roles.add("ROLE_USER");
        }

        String token = jwtTokenProvider.generateToken(request.username(), roles);
        return ResponseEntity.ok(new LoginResponse(token, request.username(), roles));
    }

    @GetMapping("/public")
    public ResponseEntity<ApiResponse> publicEndpoint() {
        return ResponseEntity.ok(ApiResponse.of(
                "Public endpoint accessible without authentication",
                Map.of("status", "ACTIVE", "scope", "PUBLIC")
        ));
    }
}
