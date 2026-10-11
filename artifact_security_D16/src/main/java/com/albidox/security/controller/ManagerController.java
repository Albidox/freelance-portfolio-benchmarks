package com.albidox.security.controller;

import com.albidox.security.dto.ApiResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/manager")
public class ManagerController {

    @GetMapping("/reports")
    @PreAuthorize("hasAnyRole('MANAGER', 'ADMIN')")
    public ResponseEntity<ApiResponse> getManagerReports(Authentication authentication) {
        return ResponseEntity.ok(ApiResponse.of(
                "Manager reports retrieved successfully",
                Map.of(
                        "department", "ENGINEERING",
                        "headcount", 42,
                        "approvedBy", authentication.getName()
                )
        ));
    }

    @PostMapping("/audit")
    @PreAuthorize("hasRole('MANAGER')")
    public ResponseEntity<ApiResponse> submitManagerAudit(
            @RequestBody(required = false) Map<String, Object> auditPayload,
            Authentication authentication) {
        return ResponseEntity.ok(ApiResponse.of(
                "Manager audit record submitted successfully",
                Map.of(
                        "auditStatus", "RECORDED",
                        "managerName", authentication.getName()
                )
        ));
    }
}
