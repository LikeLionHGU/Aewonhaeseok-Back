package com.awon.backend.auth;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "awon.auth")
public record AuthProperties(boolean required, String jwtSecret, long accessTokenSeconds,
                             String cookieName, boolean cookieSecure, String sameSite,
                             long legacyAdminId, String bootstrapAdminPassword) {
}
