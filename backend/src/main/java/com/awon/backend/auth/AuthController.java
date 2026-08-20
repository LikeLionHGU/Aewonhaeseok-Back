package com.awon.backend.auth;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Duration;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {
    private final AuthService service;
    private final AuthProperties properties;
    private final CurrentUser currentUser;

    public AuthController(AuthService service, AuthProperties properties, CurrentUser currentUser) {
        this.service = service;
        this.properties = properties;
        this.currentUser = currentUser;
    }

    @PostMapping("/register")
    @SecurityRequirements
    @Operation(summary = "회원가입", description = "성공하면 JWT를 HttpOnly 쿠키로 설정합니다.")
    public ResponseEntity<AuthService.UserResponse> register(@Valid @RequestBody RegisterRequest request) {
        return session(service.register(request.email(), request.password(), request.displayName()));
    }

    @PostMapping("/login")
    @SecurityRequirements
    @Operation(summary = "로그인", description = "성공하면 JWT를 응답 본문이 아닌 HttpOnly 쿠키로 설정합니다.")
    public ResponseEntity<AuthService.UserResponse> login(@Valid @RequestBody LoginRequest request) {
        return session(service.login(request.email(), request.password()));
    }

    @PostMapping("/logout")
    @SecurityRequirements
    public ResponseEntity<Map<String, Boolean>> logout() {
        ResponseCookie expired = cookie("").maxAge(Duration.ZERO).build();
        return ResponseEntity.ok().header(HttpHeaders.SET_COOKIE, expired.toString())
                .body(Map.of("logged_out", true));
    }

    @GetMapping("/me")
    public AuthService.UserResponse me() {
        AuthPrincipal principal = currentUser.authenticatedPrincipal();
        if (principal == null) throw new com.awon.backend.common.ApiException(
                com.awon.backend.common.ErrorCode.AUTH_REQUIRED);
        return service.me(principal.id());
    }

    private ResponseEntity<AuthService.UserResponse> session(AuthService.Session session) {
        ResponseCookie accessCookie = cookie(session.token())
                .maxAge(Duration.ofSeconds(properties.accessTokenSeconds())).build();
        return ResponseEntity.ok().header(HttpHeaders.SET_COOKIE, accessCookie.toString())
                .body(session.user());
    }

    private ResponseCookie.ResponseCookieBuilder cookie(String value) {
        return ResponseCookie.from(properties.cookieName(), value)
                .httpOnly(true).secure(properties.cookieSecure()).sameSite(properties.sameSite())
                .path("/");
    }

    public record RegisterRequest(
            @NotBlank @Email @Size(max = 320) String email,
            @NotBlank @Size(min = 8, max = 72) String password,
            @NotBlank @Size(max = 100) String displayName) { }
    public record LoginRequest(@NotBlank @Email String email, @NotBlank String password) { }
}
