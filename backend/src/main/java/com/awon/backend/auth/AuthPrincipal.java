package com.awon.backend.auth;

public record AuthPrincipal(long id, String email, String displayName, UserRole role) { }
