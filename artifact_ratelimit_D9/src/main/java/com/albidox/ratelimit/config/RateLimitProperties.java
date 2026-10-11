package com.albidox.ratelimit.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
@ConfigurationProperties(prefix = "rate-limiter")
public class RateLimitProperties {

    private boolean enabled = true;
    private long anonymousLimit = 10L;
    private long authenticatedLimit = 100L;
    private long refillDurationSeconds = 60L;
    private boolean failOpen = true;
    private List<String> trustedProxies = new ArrayList<>(List.of("127.0.0.1", "0:0:0:0:0:0:0:1", "::1"));
    private volatile boolean simulateFailure = false;

    public RateLimitProperties() {
    }

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public long getAnonymousLimit() {
        return anonymousLimit;
    }

    public void setAnonymousLimit(long anonymousLimit) {
        this.anonymousLimit = anonymousLimit;
    }

    public long getAuthenticatedLimit() {
        return authenticatedLimit;
    }

    public void setAuthenticatedLimit(long authenticatedLimit) {
        this.authenticatedLimit = authenticatedLimit;
    }

    public long getRefillDurationSeconds() {
        return refillDurationSeconds;
    }

    public void setRefillDurationSeconds(long refillDurationSeconds) {
        this.refillDurationSeconds = refillDurationSeconds;
    }

    public boolean isFailOpen() {
        return failOpen;
    }

    public void setFailOpen(boolean failOpen) {
        this.failOpen = failOpen;
    }

    public List<String> getTrustedProxies() {
        return trustedProxies;
    }

    public void setTrustedProxies(List<String> trustedProxies) {
        this.trustedProxies = trustedProxies;
    }

    public boolean isSimulateFailure() {
        return simulateFailure;
    }

    public void setSimulateFailure(boolean simulateFailure) {
        this.simulateFailure = simulateFailure;
    }
}
