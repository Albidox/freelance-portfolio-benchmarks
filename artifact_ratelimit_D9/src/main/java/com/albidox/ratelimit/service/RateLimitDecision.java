package com.albidox.ratelimit.service;

public record RateLimitDecision(
        boolean allowed,
        long remainingTokens,
        long capacity,
        long retryAfterSeconds,
        RateLimitTier tier,
        String clientKey,
        boolean degraded
) {
    public static RateLimitDecision allowed(long remainingTokens, long capacity, RateLimitTier tier, String clientKey) {
        return new RateLimitDecision(true, remainingTokens, capacity, 0L, tier, clientKey, false);
    }

    public static RateLimitDecision rejected(long capacity, long retryAfterSeconds, RateLimitTier tier, String clientKey) {
        return new RateLimitDecision(false, 0L, capacity, retryAfterSeconds, tier, clientKey, false);
    }

    public static RateLimitDecision degraded(long capacity, RateLimitTier tier, String clientKey) {
        return new RateLimitDecision(true, capacity, capacity, 0L, tier, clientKey, true);
    }
}
