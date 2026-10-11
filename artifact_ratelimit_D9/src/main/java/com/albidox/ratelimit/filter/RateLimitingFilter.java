package com.albidox.ratelimit.filter;

import com.albidox.ratelimit.config.RateLimitProperties;
import com.albidox.ratelimit.service.RateLimitDecision;
import com.albidox.ratelimit.service.RateLimitTier;
import com.albidox.ratelimit.service.RateLimiterService;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;

@Component
@Order(1)
public class RateLimitingFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(RateLimitingFilter.class);

    public static final String HEADER_API_KEY = "X-API-Key";
    public static final String HEADER_LIMIT = "X-RateLimit-Limit";
    public static final String HEADER_REMAINING = "X-RateLimit-Remaining";
    public static final String HEADER_RETRY_AFTER_SECONDS = "X-RateLimit-Retry-After-Seconds";
    public static final String HEADER_DEGRADED = "X-RateLimit-Degraded";

    private final RateLimiterService rateLimiterService;
    private final RateLimitProperties properties;

    public RateLimitingFilter(RateLimiterService rateLimiterService, RateLimitProperties properties) {
        this.rateLimiterService = rateLimiterService;
        this.properties = properties;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return !properties.isEnabled()
                || path.startsWith("/actuator")
                || path.startsWith("/api/v1/admin")
                || path.equals("/favicon.ico");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {

        long startTimeNano = System.nanoTime();

        String apiKey = request.getHeader(HEADER_API_KEY);
        RateLimitTier tier;
        String clientKey;

        if (apiKey != null && !apiKey.isBlank()) {
            tier = RateLimitTier.AUTHENTICATED;
            clientKey = "apikey:" + apiKey.trim();
        } else {
            tier = RateLimitTier.ANONYMOUS;
            String resolvedIp = resolveClientIp(request);
            clientKey = "ip:" + resolvedIp;
        }

        RateLimitDecision decision;
        try {
            decision = rateLimiterService.tryConsume(clientKey, tier);
        } catch (Exception ex) {
            log.error("Rate limiter evaluation failed for clientKey: {}. Error: {}", clientKey, ex.getMessage());
            if (properties.isFailOpen()) {
                response.setHeader(HEADER_DEGRADED, "true");
                filterChain.doFilter(request, response);
                return;
            } else {
                sendServiceUnavailable(request, response);
                return;
            }
        }

        response.setHeader(HEADER_LIMIT, String.valueOf(decision.capacity()));

        if (decision.degraded()) {
            response.setHeader(HEADER_DEGRADED, "true");
        }

        if (decision.allowed()) {
            response.setHeader(HEADER_REMAINING, String.valueOf(decision.remainingTokens()));
            filterChain.doFilter(request, response);
        } else {
            long elapsedNanos = System.nanoTime() - startTimeNano;
            double elapsedMs = elapsedNanos / 1_000_000.0;

            response.setHeader(HEADER_REMAINING, "0");
            response.setHeader(HEADER_RETRY_AFTER_SECONDS, String.valueOf(decision.retryAfterSeconds()));
            response.setHeader(HttpHeaders.RETRY_AFTER, String.valueOf(decision.retryAfterSeconds()));

            sendRateLimitExceeded(request, response, decision, elapsedMs);
        }
    }

    public String resolveClientIp(HttpServletRequest request) {
        String remoteAddr = request.getRemoteAddr();
        List<String> trusted = properties.getTrustedProxies();

        boolean isDirectHopTrusted = remoteAddr != null && (trusted.contains(remoteAddr)
                || "127.0.0.1".equals(remoteAddr)
                || "0:0:0:0:0:0:0:1".equals(remoteAddr)
                || "::1".equals(remoteAddr));

        if (!isDirectHopTrusted) {
            return remoteAddr != null ? remoteAddr : "unknown";
        }

        String xForwardedFor = request.getHeader("X-Forwarded-For");
        if (xForwardedFor == null || xForwardedFor.isBlank()) {
            return remoteAddr != null ? remoteAddr : "unknown";
        }

        String[] parts = xForwardedFor.split(",");
        for (int i = parts.length - 1; i >= 0; i--) {
            String candidate = parts[i].trim();
            if (!candidate.isEmpty() && !trusted.contains(candidate)) {
                return candidate;
            }
        }

        return parts[0].trim();
    }

    private void sendRateLimitExceeded(HttpServletRequest request,
                                       HttpServletResponse response,
                                       RateLimitDecision decision,
                                       double elapsedMs) throws IOException {

        response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
        response.setContentType(MediaType.APPLICATION_PROBLEM_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());

        String json = String.format(
                "{\"type\":\"https://api.example.com/errors/rate-limit-exceeded\"," +
                "\"title\":\"Too Many Requests\"," +
                "\"status\":429," +
                "\"detail\":\"Rate limit quota of %d requests per minute exceeded for %s. Retry after %d seconds.\"," +
                "\"tier\":\"%s\"," +
                "\"retryAfterSeconds\":%d," +
                "\"instance\":\"%s\"," +
                "\"rejectionLatencyMs\":%.3f}",
                decision.capacity(),
                decision.clientKey(),
                decision.retryAfterSeconds(),
                decision.tier().name(),
                decision.retryAfterSeconds(),
                request.getRequestURI(),
                elapsedMs
        );

        byte[] bytes = json.getBytes(StandardCharsets.UTF_8);
        response.setContentLength(bytes.length);
        response.getOutputStream().write(bytes);
        response.getOutputStream().flush();
    }

    private void sendServiceUnavailable(HttpServletRequest request, HttpServletResponse response) throws IOException {
        response.setStatus(HttpStatus.SERVICE_UNAVAILABLE.value());
        response.setContentType(MediaType.APPLICATION_PROBLEM_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());

        String json = String.format(
                "{\"type\":\"https://api.example.com/errors/service-unavailable\"," +
                "\"title\":\"Service Unavailable\"," +
                "\"status\":503," +
                "\"detail\":\"Rate limiter subsystem currently unavailable.\"," +
                "\"instance\":\"%s\"}",
                request.getRequestURI()
        );

        byte[] bytes = json.getBytes(StandardCharsets.UTF_8);
        response.setContentLength(bytes.length);
        response.getOutputStream().write(bytes);
        response.getOutputStream().flush();
    }
}
