package com.awon.backend.auth;

import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class LegacyAdminBootstrap {
    private final AuthProperties properties;
    private final AppUserRepository users;
    private final PasswordEncoder passwords;

    public LegacyAdminBootstrap(AuthProperties properties, AppUserRepository users,
                                PasswordEncoder passwords) {
        this.properties = properties;
        this.users = users;
        this.passwords = passwords;
    }

    @EventListener(ApplicationReadyEvent.class)
    @Transactional
    public void initializePassword() {
        String password = properties.bootstrapAdminPassword();
        if (password == null || password.isBlank()) return;
        users.findById(properties.legacyAdminId())
                .filter(user -> "{disabled}".equals(user.getPasswordHash()))
                .ifPresent(user -> user.setPasswordHash(passwords.encode(password)));
    }
}
