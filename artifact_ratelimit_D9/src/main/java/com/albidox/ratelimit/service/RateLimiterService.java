package com.albidox.ratelimit.service;

import com.albidox.ratelimit.config.RateLimitProperties;
import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import io.github.bucket4j.Bandwidth;
import io.github.bucket4j.Bucket;
import io.github.bucket4j.ConsumptionProbe;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.concurrent.TimeUnit;

@Service
public class RateLimiterService {

    private static final Logger log = LoggerFactory.getLogger(RateLimiterService.class);

    private final RateLimitProperties properties;
    private final Cache<String, Bucket> bucketCache;

    public RateLimiterService(RateLimitProperties properties) {
        this.properties = properties;
        this.bucketCache = Caffeine.newBuilder()
                .maximumSize(100_000)
                .expireAfterAccess(Duration.ofMinutes(15))
                .build();
    }

    public RateLimitDecision tryConsume(String clientKey, RateLimitTier tier) {
        long capacity = resolveCapacity(tier);

        if (properties.isSimulateFailure()) {
            if (properties.isFailOpen()) {
                log.warn("Rate limiter failure simulated. Failing open for client: {}", clientKey);
                return RateLimitDecision.degraded(capacity, tier, clientKey);
            } else {
                throw new IllegalStateException("Rate limiter backend failure: simulated outage");
            }
        }

        Bucket bucket = bucketCache.get(clientKey, key -> createBucket(capacity, properties.getRefillDurationSeconds()));
        if (bucket == null) {
            throw new IllegalStateException("Failed to initialize rate limiter bucket for key: " + clientKey);
        }

        ConsumptionProbe probe = bucket.tryConsumeAndReturnRemaining(1);
        if (probe.isConsumed()) {
            return RateLimitDecision.allowed(probe.getRemainingTokens(), capacity, tier, clientKey);
        }

        long nanosToWait = probe.getNanosToWaitForRefill();
        long retryAfterSeconds = Math.max(1L, TimeUnit.NANOSECONDS.toSeconds(nanosToWait));
        return RateLimitDecision.rejected(capacity, retryAfterSeconds, tier, clientKey);
    }

    public long resolveCapacity(RateLimitTier tier) {
        return switch (tier) {
            case ANONYMOUS -> properties.getAnonymousLimit();
            case AUTHENTICATED -> properties.getAuthenticatedLimit();
        };
    }

    private Bucket createBucket(long capacity, long refillDurationSeconds) {
        Bandwidth limit = Bandwidth.builder()
                .capacity(capacity)
                .refillGreedy(capacity, Duration.ofSeconds(refillDurationSeconds))
                .build();
        return Bucket.builder()
                .addLimit(limit)
                .build();
    }

    public void clearAll() {
        bucketCache.invalidateAll();
    }

    public void resetKey(String clientKey) {
        bucketCache.invalidate(clientKey);
    }
}
