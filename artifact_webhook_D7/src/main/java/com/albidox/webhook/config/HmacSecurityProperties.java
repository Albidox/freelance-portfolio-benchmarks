package com.albidox.webhook.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@ConfigurationProperties(prefix = "webhook.security")
public class HmacSecurityProperties {

    private String hmacSecret = "webhook-secret-key-prod-d7-secure-2026";
    private long toleranceSeconds = 300L;

    public String getHmacSecret() {
        return hmacSecret;
    }

    public void setHmacSecret(String hmacSecret) {
        this.hmacSecret = hmacSecret;
    }

    public long getToleranceSeconds() {
        return toleranceSeconds;
    }

    public void setToleranceSeconds(long toleranceSeconds) {
        this.toleranceSeconds = toleranceSeconds;
    }
}
