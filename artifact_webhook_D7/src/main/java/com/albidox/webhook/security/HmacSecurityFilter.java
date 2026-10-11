package com.albidox.webhook.security;

import com.albidox.webhook.config.HmacSecurityProperties;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.InvalidKeyException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;

@Component
@Order(1)
public class HmacSecurityFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(HmacSecurityFilter.class);
    private static final String HMAC_ALGORITHM = "HmacSHA256";

    private final HmacSecurityProperties properties;

    public HmacSecurityFilter(HmacSecurityProperties properties) {
        this.properties = properties;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return !path.startsWith("/api/v1/webhooks/payments");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {

        String timestampHeader = request.getHeader("X-Timestamp");
        String signatureHeader = request.getHeader("X-Signature");

        if (timestampHeader == null || timestampHeader.isBlank()) {
            sendErrorResponse(response, HttpServletResponse.SC_BAD_REQUEST, "Missing required X-Timestamp header");
            return;
        }

        long timestamp;
        try {
            timestamp = Long.parseLong(timestampHeader.trim());
        } catch (NumberFormatException e) {
            sendErrorResponse(response, HttpServletResponse.SC_BAD_REQUEST, "Invalid X-Timestamp header format: numeric epoch required");
            return;
        }

        long currentEpochSecond = Instant.now().getEpochSecond();
        long ageSeconds = currentEpochSecond - timestamp;
        if (ageSeconds > properties.getToleranceSeconds() || ageSeconds < -properties.getToleranceSeconds()) {
            log.warn("Timestamp validation failed: age={}s exceeds tolerance={}s", ageSeconds, properties.getToleranceSeconds());
            sendErrorResponse(response, HttpServletResponse.SC_BAD_REQUEST, "Timestamp outside allowed tolerance window (300s)");
            return;
        }

        if (signatureHeader == null || signatureHeader.isBlank()) {
            sendErrorResponse(response, HttpServletResponse.SC_UNAUTHORIZED, "Missing required X-Signature header");
            return;
        }

        CachedBodyHttpServletRequest cachedRequest = new CachedBodyHttpServletRequest(request);
        String rawBody = cachedRequest.getBodyAsString();

        long verifyStartNanos = System.nanoTime();
        String expectedSignatureHex;
        try {
            expectedSignatureHex = calculateHmacSha256(properties.getHmacSecret(), timestampHeader.trim() + "." + rawBody);
        } catch (NoSuchAlgorithmException | InvalidKeyException e) {
            log.error("Failed to compute HMAC SHA-256 signature", e);
            sendErrorResponse(response, HttpServletResponse.SC_INTERNAL_SERVER_ERROR, "Signature computation error");
            return;
        }

        String providedSignature = cleanSignatureHeader(signatureHeader);

        byte[] expectedBytes = expectedSignatureHex.toLowerCase().getBytes(StandardCharsets.UTF_8);
        byte[] providedBytes = providedSignature.toLowerCase().getBytes(StandardCharsets.UTF_8);

        boolean signatureMatches = MessageDigest.isEqual(expectedBytes, providedBytes);
        long verifyDurationNanos = System.nanoTime() - verifyStartNanos;

        response.setHeader("X-Verification-Time-Nanos", String.valueOf(verifyDurationNanos));
        response.setHeader("X-Verification-Time-Micros", String.format(java.util.Locale.ROOT, "%.3f", verifyDurationNanos / 1000.0));

        if (!signatureMatches) {
            log.warn("HMAC signature verification failed: constant-time mismatch in {} ns ({} ms)",
                    verifyDurationNanos, String.format(java.util.Locale.ROOT, "%.4f", verifyDurationNanos / 1_000_000.0));
            sendErrorResponse(response, HttpServletResponse.SC_UNAUTHORIZED, "Invalid HMAC signature");
            return;
        }

        filterChain.doFilter(cachedRequest, response);
    }

    private String calculateHmacSha256(String secret, String data) throws NoSuchAlgorithmException, InvalidKeyException {
        Mac mac = Mac.getInstance(HMAC_ALGORITHM);
        SecretKeySpec secretKeySpec = new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), HMAC_ALGORITHM);
        mac.init(secretKeySpec);
        byte[] rawHmac = mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
        return HexFormat.of().formatHex(rawHmac);
    }

    private String cleanSignatureHeader(String header) {
        String clean = header.trim();
        if (clean.startsWith("sha256=")) {
            return clean.substring(7);
        }
        if (clean.startsWith("v1=")) {
            return clean.substring(3);
        }
        return clean;
    }

    private void sendErrorResponse(HttpServletResponse response, int statusCode, String message) throws IOException {
        response.setStatus(statusCode);
        response.setContentType("application/json");
        response.setCharacterEncoding("UTF-8");
        String payload = String.format("{\"status\":\"error\",\"code\":%d,\"message\":\"%s\"}", statusCode, message);
        response.getWriter().write(payload);
    }
}
