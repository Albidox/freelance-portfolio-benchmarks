package com.albidox.jvmopt.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.lang.management.ManagementFactory;
import java.lang.management.MemoryMXBean;
import java.lang.management.RuntimeMXBean;
import java.util.Map;

@RestController
@RequestMapping("/api/v1")
public class StatusController {

    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> getStatus() {
        RuntimeMXBean runtimeBean = ManagementFactory.getRuntimeMXBean();
        MemoryMXBean memoryBean = ManagementFactory.getMemoryMXBean();

        long uptimeMs = runtimeBean.getUptime();
        long heapUsedBytes = memoryBean.getHeapMemoryUsage().getUsed();
        long heapMaxBytes = memoryBean.getHeapMemoryUsage().getMax();

        Map<String, Object> payload = Map.of(
            "service", "artifact-jvm-d4",
            "status", "OPTIMIZED_RUNTIME_ACTIVE",
            "uptime_ms", uptimeMs,
            "heap_used_mb", heapUsedBytes / (1024 * 1024),
            "heap_max_mb", heapMaxBytes / (1024 * 1024),
            "vm_name", runtimeBean.getVmName(),
            "vm_version", runtimeBean.getVmVersion()
        );

        return ResponseEntity.ok(payload);
    }
}
