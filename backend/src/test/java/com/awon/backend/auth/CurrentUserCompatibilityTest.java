package com.awon.backend.auth;

import com.awon.backend.common.ApiException;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.core.context.SecurityContextHolder;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class CurrentUserCompatibilityTest {
    @AfterEach void clear() { SecurityContextHolder.clearContext(); }

    @Test
    void anonymousUsesLegacyAdminOnlyWhenAuthIsOptional() {
        assertEquals(1L, new CurrentUser(properties(false)).id());
        assertThrows(ApiException.class, () -> new CurrentUser(properties(true)).id());
    }

    private AuthProperties properties(boolean required) {
        return new AuthProperties(required, "x".repeat(32), 3600,
                "AWON_ACCESS_TOKEN", false, "Strict", 1, "");
    }
}
