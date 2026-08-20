package com.awon.backend.auth;

import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import tools.jackson.databind.ObjectMapper;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class JwtServiceTest {
    private static final String SECRET = "test-secret-with-at-least-thirty-two-bytes-123";
    private static final Instant NOW = Instant.parse("2026-08-19T00:00:00Z");

    @Test
    void signedTokenRoundTripsAndTamperingIsRejected() {
        JwtService service = serviceAt(NOW);
        AppUser user = new AppUser("user@example.com", "hash", "사용자");
        ReflectionTestUtils.setField(user, "id", 42L);

        String token = service.issue(user);
        assertEquals(42L, service.verify(token).userId());
        assertThrows(JwtService.InvalidTokenException.class,
                () -> service.verify(token.substring(0, token.length() - 1) + "x"));
    }

    @Test
    void expiredTokenIsRejected() {
        AppUser user = new AppUser("user@example.com", "hash", "사용자");
        ReflectionTestUtils.setField(user, "id", 42L);
        String token = serviceAt(NOW).issue(user);
        JwtService expiredVerifier = new JwtService(SECRET, 60, new ObjectMapper(),
                Clock.fixed(NOW.plusSeconds(61), ZoneOffset.UTC));
        assertThrows(JwtService.InvalidTokenException.class, () -> expiredVerifier.verify(token));
    }

    private JwtService serviceAt(Instant instant) {
        return new JwtService(SECRET, 60, new ObjectMapper(),
                Clock.fixed(instant, ZoneOffset.UTC));
    }
}
