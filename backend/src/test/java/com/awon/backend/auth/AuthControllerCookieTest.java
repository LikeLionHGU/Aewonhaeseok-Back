package com.awon.backend.auth;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class AuthControllerCookieTest {
    @Test
    void loginReturnsJwtOnlyInHttpOnlyCookie() {
        AuthService service = mock(AuthService.class);
        AuthProperties properties = new AuthProperties(false, "x".repeat(32), 3600,
                "AWON_ACCESS_TOKEN", true, "Strict", 1, "");
        AuthController controller = new AuthController(service, properties, mock(CurrentUser.class));
        var user = new AuthService.UserResponse(2, "user@example.com", "사용자", UserRole.USER);
        when(service.login("user@example.com", "password123"))
                .thenReturn(new AuthService.Session(user, "signed.jwt.value"));

        var response = controller.login(
                new AuthController.LoginRequest("user@example.com", "password123"));
        String cookie = response.getHeaders().getFirst(HttpHeaders.SET_COOKIE);

        assertTrue(cookie.contains("HttpOnly"));
        assertTrue(cookie.contains("Secure"));
        assertTrue(cookie.contains("SameSite=Strict"));
        assertFalse(response.getBody().toString().contains("signed.jwt.value"));
    }
}
