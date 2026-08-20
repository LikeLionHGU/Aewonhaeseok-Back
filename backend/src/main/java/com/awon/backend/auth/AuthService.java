package com.awon.backend.auth;

import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Locale;
import java.util.Map;

@Service
public class AuthService {
    private final AppUserRepository users;
    private final PasswordEncoder passwords;
    private final JwtService jwt;

    public AuthService(AppUserRepository users, PasswordEncoder passwords, JwtService jwt) {
        this.users = users;
        this.passwords = passwords;
        this.jwt = jwt;
    }

    @Transactional
    public Session register(String email, String password, String displayName) {
        String normalized = normalize(email);
        if (users.existsByEmail(normalized)) throw duplicateEmail(normalized);
        try {
            AppUser user = users.save(new AppUser(normalized, passwords.encode(password),
                    displayName.trim()));
            return new Session(UserResponse.of(user), jwt.issue(user));
        } catch (DataIntegrityViolationException e) {
            throw duplicateEmail(normalized);
        }
    }

    @Transactional(readOnly = true)
    public Session login(String email, String password) {
        AppUser user = users.findByEmail(normalize(email))
                .filter(AppUser::isEnabled)
                .filter(found -> passwords.matches(password, found.getPasswordHash()))
                .orElseThrow(() -> new ApiException(ErrorCode.AUTH_INVALID_CREDENTIALS));
        return new Session(UserResponse.of(user), jwt.issue(user));
    }

    @Transactional(readOnly = true)
    public UserResponse me(long userId) {
        AppUser user = users.findById(userId).filter(AppUser::isEnabled)
                .orElseThrow(() -> new ApiException(ErrorCode.AUTH_REQUIRED));
        return UserResponse.of(user);
    }

    private String normalize(String email) {
        return email == null ? "" : email.trim().toLowerCase(Locale.ROOT);
    }

    private ApiException duplicateEmail(String email) {
        return new ApiException(ErrorCode.AUTH_EMAIL_ALREADY_USED, Map.of("email", email));
    }

    public record Session(UserResponse user, String token) { }
    public record UserResponse(long id, String email, String displayName, UserRole role) {
        static UserResponse of(AppUser user) {
            return new UserResponse(user.getId(), user.getEmail(), user.getDisplayName(), user.getRole());
        }
    }
}
