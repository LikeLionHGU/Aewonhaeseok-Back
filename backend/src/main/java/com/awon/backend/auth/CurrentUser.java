package com.awon.backend.auth;

import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;

@Component
public class CurrentUser {
    private final AuthProperties properties;

    public CurrentUser(AuthProperties properties) { this.properties = properties; }

    public long id() {
        AuthPrincipal principal = authenticatedPrincipal();
        if (principal != null) return principal.id();
        if (!properties.required()) return properties.legacyAdminId();
        throw new ApiException(ErrorCode.AUTH_REQUIRED);
    }

    public AuthPrincipal authenticatedPrincipal() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication != null && authentication.isAuthenticated()
                && authentication.getPrincipal() instanceof AuthPrincipal principal) {
            return principal;
        }
        return null;
    }

    public String reviewerName(String fallback) {
        AuthPrincipal principal = authenticatedPrincipal();
        return principal == null ? fallback : principal.displayName();
    }
}
