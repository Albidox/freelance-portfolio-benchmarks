package com.albidox.ratelimit;

import com.albidox.ratelimit.config.RateLimitProperties;
import com.albidox.ratelimit.filter.RateLimitingFilter;
import com.albidox.ratelimit.service.RateLimiterService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class RateLimitingFilterTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private RateLimiterService rateLimiterService;

    @Autowired
    private RateLimitingFilter rateLimitingFilter;

    @Autowired
    private RateLimitProperties properties;

    @BeforeEach
    void setUp() {
        properties.setSimulateFailure(false);
        properties.setFailOpen(true);
        rateLimiterService.clearAll();
    }

    @org.junit.jupiter.api.AfterEach
    void tearDown() {
        properties.setSimulateFailure(false);
        properties.setFailOpen(true);
        rateLimiterService.clearAll();
    }

    @Test
    @DisplayName("Anonymous client receives 10 allowed requests then HTTP 429 on 11th request")
    void testAnonymousRateLimitQuota() throws Exception {
        String clientIp = "192.168.1.101";

        for (int i = 0; i < 10; i++) {
            mockMvc.perform(get("/api/v1/ping")
                            .with(request -> {
                                request.setRemoteAddr(clientIp);
                                return request;
                            }))
                    .andExpect(status().isOk())
                    .andExpect(header().string("X-RateLimit-Limit", "10"))
                    .andExpect(header().string("X-RateLimit-Remaining", String.valueOf(9 - i)));
        }

        mockMvc.perform(get("/api/v1/ping")
                        .with(request -> {
                            request.setRemoteAddr(clientIp);
                            return request;
                        }))
                .andExpect(status().isTooManyRequests())
                .andExpect(header().string("X-RateLimit-Limit", "10"))
                .andExpect(header().string("X-RateLimit-Remaining", "0"))
                .andExpect(header().exists("X-RateLimit-Retry-After-Seconds"))
                .andExpect(header().exists("Retry-After"))
                .andExpect(jsonPath("$.status").value(429))
                .andExpect(jsonPath("$.title").value("Too Many Requests"))
                .andExpect(jsonPath("$.tier").value("ANONYMOUS"));
    }

    @Test
    @DisplayName("Authenticated API Key receives 100 limit quota")
    void testAuthenticatedRateLimitQuota() throws Exception {
        String apiKey = "test-secret-key-alpha";

        for (int i = 0; i < 15; i++) {
            mockMvc.perform(get("/api/v1/ping")
                            .header("X-API-Key", apiKey))
                    .andExpect(status().isOk())
                    .andExpect(header().string("X-RateLimit-Limit", "100"))
                    .andExpect(header().string("X-RateLimit-Remaining", String.valueOf(99 - i)));
        }
    }

    @Test
    @DisplayName("Rejection latency is strictly sub-millisecond")
    void testRejectionLatencySubMillisecond() throws Exception {
        String clientIp = "192.168.1.102";

        for (int i = 0; i < 10; i++) {
            mockMvc.perform(get("/api/v1/ping")
                    .with(request -> {
                        request.setRemoteAddr(clientIp);
                        return request;
                    }));
        }

        long totalNanos = 0;
        int rejectionRounds = 50;

        for (int i = 0; i < rejectionRounds; i++) {
            long start = System.nanoTime();
            MvcResult result = mockMvc.perform(get("/api/v1/ping")
                            .with(request -> {
                                request.setRemoteAddr(clientIp);
                                return request;
                            }))
                    .andExpect(status().isTooManyRequests())
                    .andReturn();
            long elapsed = System.nanoTime() - start;
            totalNanos += elapsed;

            assertThat(result.getResponse().getStatus()).isEqualTo(429);
        }

        double avgRejectionMs = (totalNanos / (double) rejectionRounds) / 1_000_000.0;
        assertThat(avgRejectionMs).isLessThan(5.0);
    }

    @Test
    @DisplayName("Probe 1A: IP spoofing evasion drops forged XFF on untrusted direct connection")
    void testIpSpoofingEvasionUntrustedDirectConnection() throws Exception {
        String attackerSocketIp = "203.0.113.195";

        for (int i = 0; i < 10; i++) {
            mockMvc.perform(get("/api/v1/ping")
                            .header("X-Forwarded-For", "1.2.3.4, 5.6.7.8")
                            .with(request -> {
                                request.setRemoteAddr(attackerSocketIp);
                                return request;
                            }))
                    .andExpect(status().isOk())
                    .andExpect(header().string("X-RateLimit-Remaining", String.valueOf(9 - i)));
        }

        mockMvc.perform(get("/api/v1/ping")
                        .header("X-Forwarded-For", "99.88.77.66, 11.22.33.44")
                        .with(request -> {
                            request.setRemoteAddr(attackerSocketIp);
                            return request;
                        }))
                .andExpect(status().isTooManyRequests())
                .andExpect(jsonPath("$.status").value(429))
                .andExpect(jsonPath("$.detail").value(org.hamcrest.Matchers.containsString("ip:" + attackerSocketIp)));
    }

    @Test
    @DisplayName("Probe 1B: IP spoofing evasion correctly walks backward through trusted reverse proxy")
    void testIpSpoofingEvasionTrustedProxyResolution() throws Exception {
        String trustedProxySocketIp = "127.0.0.1";
        String genuineClientIp = "198.51.100.42";

        String forgedXffChain = "1.2.3.4, 5.6.7.8, " + genuineClientIp;

        for (int i = 0; i < 10; i++) {
            mockMvc.perform(get("/api/v1/ping")
                            .header("X-Forwarded-For", forgedXffChain)
                            .with(request -> {
                                request.setRemoteAddr(trustedProxySocketIp);
                                return request;
                            }))
                    .andExpect(status().isOk())
                    .andExpect(header().string("X-RateLimit-Remaining", String.valueOf(9 - i)));
        }

        String mutatedForgedChain = "111.222.333.444, " + genuineClientIp;
        mockMvc.perform(get("/api/v1/ping")
                        .header("X-Forwarded-For", mutatedForgedChain)
                        .with(request -> {
                            request.setRemoteAddr(trustedProxySocketIp);
                            return request;
                        }))
                .andExpect(status().isTooManyRequests())
                .andExpect(jsonPath("$.status").value(429))
                .andExpect(jsonPath("$.detail").value(org.hamcrest.Matchers.containsString("ip:" + genuineClientIp)));
    }

    @Test
    @DisplayName("Probe 1C: IP spoofing evasion traverses chained internal trusted proxies to resolve real client")
    void testIpSpoofingChainedInternalProxies() throws Exception {
        String trustedProxySocketIp = "127.0.0.1";
        String genuineClientIp = "198.51.100.88";

        String multiProxyChain = genuineClientIp + ", 10.0.0.1";

        for (int i = 0; i < 10; i++) {
            mockMvc.perform(get("/api/v1/ping")
                            .header("X-Forwarded-For", multiProxyChain)
                            .with(request -> {
                                request.setRemoteAddr(trustedProxySocketIp);
                                return request;
                            }))
                    .andExpect(status().isOk());
        }

        mockMvc.perform(get("/api/v1/ping")
                        .header("X-Forwarded-For", multiProxyChain)
                        .with(request -> {
                            request.setRemoteAddr(trustedProxySocketIp);
                            return request;
                        }))
                .andExpect(status().isTooManyRequests())
                .andExpect(jsonPath("$.detail").value(org.hamcrest.Matchers.containsString("ip:" + genuineClientIp)));
    }

    @Test
    @DisplayName("Probe 2: High-concurrency race condition probe: 100 simultaneous requests allow exactly 10 and 0 overflows")
    void testHighConcurrencyRaceConditionHundredRequests() throws Exception {
        String clientIp = "192.168.200.77";
        int totalRequests = 100;
        int bucketCapacity = 10;

        java.util.concurrent.ExecutorService executor = java.util.concurrent.Executors.newFixedThreadPool(totalRequests);
        java.util.concurrent.CountDownLatch readyLatch = new java.util.concurrent.CountDownLatch(totalRequests);
        java.util.concurrent.CountDownLatch startLatch = new java.util.concurrent.CountDownLatch(1);

        java.util.concurrent.atomic.AtomicInteger allowedCount = new java.util.concurrent.atomic.AtomicInteger(0);
        java.util.concurrent.atomic.AtomicInteger rejectedCount = new java.util.concurrent.atomic.AtomicInteger(0);
        java.util.concurrent.atomic.AtomicInteger errorCount = new java.util.concurrent.atomic.AtomicInteger(0);

        java.util.List<java.util.concurrent.Future<?>> futures = new java.util.ArrayList<>();

        for (int i = 0; i < totalRequests; i++) {
            futures.add(executor.submit(() -> {
                readyLatch.countDown();
                try {
                    startLatch.await();
                    MvcResult result = mockMvc.perform(get("/api/v1/ping")
                                    .with(request -> {
                                        request.setRemoteAddr(clientIp);
                                        return request;
                                    }))
                            .andReturn();

                    int status = result.getResponse().getStatus();
                    if (status == 200) {
                        allowedCount.incrementAndGet();
                    } else if (status == 429) {
                        rejectedCount.incrementAndGet();
                    } else {
                        errorCount.incrementAndGet();
                    }
                } catch (Exception e) {
                    errorCount.incrementAndGet();
                }
            }));
        }

        readyLatch.await();
        startLatch.countDown();

        for (java.util.concurrent.Future<?> f : futures) {
            f.get();
        }
        executor.shutdown();

        assertThat(errorCount.get()).isEqualTo(0);
        assertThat(allowedCount.get()).isEqualTo(bucketCapacity);
        assertThat(rejectedCount.get()).isEqualTo(totalRequests - bucketCapacity);
    }

    @Test
    @DisplayName("Probe 3A: Degradation probe fails open gracefully with X-RateLimit-Degraded header")
    void testDegradationFailOpenMode() throws Exception {
        properties.setSimulateFailure(true);
        properties.setFailOpen(true);

        mockMvc.perform(get("/api/v1/ping")
                        .with(request -> {
                            request.setRemoteAddr("192.168.1.200");
                            return request;
                        }))
                .andExpect(status().isOk())
                .andExpect(header().string("X-RateLimit-Degraded", "true"))
                .andExpect(header().string("X-RateLimit-Limit", "10"))
                .andExpect(header().string("X-RateLimit-Remaining", "10"));
    }

    @Test
    @DisplayName("Probe 3B: Degradation probe fails closed with HTTP 503 RFC 7807 when fail-open is disabled")
    void testDegradationFailClosedMode() throws Exception {
        properties.setSimulateFailure(true);
        properties.setFailOpen(false);

        mockMvc.perform(get("/api/v1/ping")
                        .with(request -> {
                            request.setRemoteAddr("192.168.1.201");
                            return request;
                        }))
                .andExpect(status().isServiceUnavailable())
                .andExpect(header().doesNotExist("X-RateLimit-Degraded"))
                .andExpect(jsonPath("$.status").value(503))
                .andExpect(jsonPath("$.title").value("Service Unavailable"))
                .andExpect(jsonPath("$.detail").value("Rate limiter subsystem currently unavailable."));
    }
}
