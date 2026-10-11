package com.example.security;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class ApiController {

    @GetMapping("/public/health")
    public String health() {
        return "OK";
    }

    @GetMapping("/user/profile")
    public String profile() {
        return "User Profile";
    }

    @GetMapping("/admin/metrics")
    public String metrics() {
        return "Admin Metrics";
    }
}
