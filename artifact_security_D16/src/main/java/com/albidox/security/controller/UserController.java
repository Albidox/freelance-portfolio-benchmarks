package com.albidox.security.controller;

import com.albidox.security.dto.ApiResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/user")
public class UserController {

    @GetMapping("/profile")
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<ApiResponse> getUserProfile(Authentication authentication) {
        return ResponseEntity.ok(ApiResponse.of(
                "User profile retrieved successfully",
                Map.of(
                        "username", authentication.getName(),
                        "authorities", authentication.getAuthorities().toString()
                )
        ));
    }

    @GetMapping("/data")
    @PreAuthorize("hasRole('USER')")
    public ResponseEntity<ApiResponse> getUserSpecificData(Authentication authentication) {
        return ResponseEntity.ok(ApiResponse.of(
                "User specific personal data retrieved successfully",
                Map.of(
                        "username", authentication.getName(),
                        "tier", "STANDARD_USER"
                )
        ));
    }

    @PutMapping("/settings")
    @PreAuthorize("hasAnyRole('USER', 'ADMIN')")
    public ResponseEntity<ApiResponse> updateUserSettings(
            @RequestBody(required = false) Map<String, Object> settings,
            Authentication authentication) {
        return ResponseEntity.ok(ApiResponse.of(
                "User settings updated successfully",
                Map.of(
                        "username", authentication.getName(),
                        "updatedBy", authentication.getName()
                )
        ));
    }
}
