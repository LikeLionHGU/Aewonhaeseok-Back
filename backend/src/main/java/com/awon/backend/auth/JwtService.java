package com.awon.backend.auth;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Autowired;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Clock;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class JwtService {
    private static final Base64.Encoder ENCODER = Base64.getUrlEncoder().withoutPadding();
    private static final Base64.Decoder DECODER = Base64.getUrlDecoder();
    private final byte[] secret;
    private final long lifetimeSeconds;
    private final ObjectMapper json;
    private final Clock clock;

    @Autowired
    public JwtService(AuthProperties properties, ObjectMapper json) {
        this(properties.jwtSecret(), properties.accessTokenSeconds(), json, Clock.systemUTC());
    }

    JwtService(String secret, long lifetimeSeconds, ObjectMapper json, Clock clock) {
        if (secret == null || secret.getBytes(StandardCharsets.UTF_8).length < 32) {
            throw new IllegalStateException("JWT_SECRET은 32바이트 이상이어야 합니다.");
        }
        this.secret = secret.getBytes(StandardCharsets.UTF_8);
        this.lifetimeSeconds = lifetimeSeconds;
        this.json = json;
        this.clock = clock;
    }

    public String issue(AppUser user) {
        Instant now = clock.instant();
        String header = encode(Map.of("alg", "HS256", "typ", "JWT"));
        Map<String, Object> claims = new LinkedHashMap<>();
        claims.put("sub", String.valueOf(user.getId()));
        claims.put("email", user.getEmail());
        claims.put("role", user.getRole().name());
        claims.put("iat", now.getEpochSecond());
        claims.put("exp", now.plusSeconds(lifetimeSeconds).getEpochSecond());
        String payload = encode(claims);
        String unsigned = header + "." + payload;
        return unsigned + "." + ENCODER.encodeToString(sign(unsigned));
    }

    public Claims verify(String token) {
        try {
            String[] parts = token.split("\\.");
            if (parts.length != 3) throw new InvalidTokenException();
            byte[] expected = sign(parts[0] + "." + parts[1]);
            if (!MessageDigest.isEqual(expected, DECODER.decode(parts[2]))) {
                throw new InvalidTokenException();
            }
            JsonNode header = json.readTree(DECODER.decode(parts[0]));
            if (!"HS256".equals(header.path("alg").asText())) throw new InvalidTokenException();
            JsonNode body = json.readTree(DECODER.decode(parts[1]));
            long expiresAt = body.path("exp").asLong(0);
            if (expiresAt <= clock.instant().getEpochSecond()) throw new InvalidTokenException();
            long userId = Long.parseLong(body.path("sub").asText());
            return new Claims(userId, body.path("email").asText(),
                    UserRole.valueOf(body.path("role").asText()), expiresAt);
        } catch (InvalidTokenException e) {
            throw e;
        } catch (RuntimeException e) {
            throw new InvalidTokenException();
        }
    }

    private String encode(Object value) {
        return ENCODER.encodeToString(json.writeValueAsBytes(value));
    }

    private byte[] sign(String value) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret, "HmacSHA256"));
            return mac.doFinal(value.getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) {
            throw new IllegalStateException("JWT 서명 실패", e);
        }
    }

    public record Claims(long userId, String email, UserRole role, long expiresAt) { }
    public static final class InvalidTokenException extends RuntimeException { }
}
