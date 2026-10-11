package com.albidox.security.controller;

import com.albidox.security.dto.ApiResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/admin")
public class AdminController {

    @GetMapping("/dashboard")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse> getAdminDashboard(Authentication authentication) {
        return ResponseEntity.ok(ApiResponse.of(
                "Admin dashboard metrics retrieved successfully",
                Map.of(
                        "systemStatus", "OPERATIONAL",
                        "activeNodes", 8,
                        "securityEnforcement", "STRICT_RBAC",
                        "accessedBy", authentication.getName()
                )
        ));
    }

    @PostMapping("/settings")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse> updateSystemSettings(
            @RequestBody(required = false) Map<String, Object> settings,
            Authentication authentication) {
        return ResponseEntity.ok(ApiResponse.of(
                "System settings applied successfully",
                Map.of(
                        "status", "APPLIED",
                        "updatedBy", authentication.getName()
                )
        ));
    }

    @DeleteMapping("/users/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse> deleteUser(
            @PathVariable("id") Long id,
            Authentication authentication) {
        return ResponseEntity.ok(ApiResponse.of(
                "User deleted successfully",
                Map.of(
                        "deletedUserId", id,
                        "actionBy", authentication.getName()
                )
        ));
    }
}
