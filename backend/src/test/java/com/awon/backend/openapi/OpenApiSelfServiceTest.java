package com.awon.backend.openapi;

import com.awon.backend.auth.CurrentUser;
import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class OpenApiSelfServiceTest {
    private OrganizationRepository organizations;
    private OrganizationApiKeyRepository keys;
    private OpenApiKeyService keyService;
    private CurrentUser currentUser;
    private OpenApiSelfService service;

    @BeforeEach
    void setUp() {
        organizations = mock(OrganizationRepository.class);
        keys = mock(OrganizationApiKeyRepository.class);
        keyService = mock(OpenApiKeyService.class);
        currentUser = mock(CurrentUser.class);
        service = new OpenApiSelfService(organizations, keys, keyService, currentUser);
        when(currentUser.id()).thenReturn(42L);
    }

    @Test
    void firstIssueCreatesOrganizationOwnedByCurrentUser() {
        when(organizations.findOwnedForUpdate(42L)).thenReturn(Optional.empty());
        when(organizations.existsByName("어원환경")).thenReturn(false);
        AtomicReference<Organization> savedOrganization = new AtomicReference<>();
        when(organizations.save(any())).thenAnswer(invocation -> {
            Organization organization = invocation.getArgument(0);
            ReflectionTestUtils.setField(organization, "id", 8L);
            savedOrganization.set(organization);
            return organization;
        });
        when(keys.countByOrganizationIdAndActiveTrue(8L)).thenReturn(0L);
        OrganizationApiKey key = key(3L, 8L, true);
        when(keyService.issue(8L, "운영 서버", 60))
                .thenReturn(new OpenApiKeyService.IssuedKey(key, "awon_live_once"));

        var response = service.issue(" 어원환경 ", "운영 서버", 60);

        assertEquals("어원환경", response.organization().name());
        assertEquals("awon_live_once", response.apiKey());
        assertEquals(42L, savedOrganization.get().getOwnerUserId());
        verify(keyService).issue(8L, "운영 서버", 60);
    }

    @Test
    void existingOwnerCannotSwitchToAnotherOrganizationName() {
        Organization owned = ownedOrganization(8L, "어원환경", 42L);
        when(organizations.findOwnedForUpdate(42L)).thenReturn(Optional.of(owned));

        ApiException exception = assertThrows(ApiException.class,
                () -> service.issue("다른기업", "운영 서버", 60));

        assertEquals(ErrorCode.OPEN_API_ORGANIZATION_FORBIDDEN, exception.errorCode());
        verify(keyService, never()).issue(anyLong(), anyString(), anyInt());
    }

    @Test
    void existingOrganizationNameOwnedBySomeoneElseIsRejected() {
        when(organizations.findOwnedForUpdate(42L)).thenReturn(Optional.empty());
        when(organizations.existsByName("남의기업")).thenReturn(true);

        ApiException exception = assertThrows(ApiException.class,
                () -> service.issue("남의기업", "운영 서버", 60));

        assertEquals(ErrorCode.OPEN_API_ORGANIZATION_FORBIDDEN, exception.errorCode());
        verify(organizations, never()).save(any());
    }

    @Test
    void activeKeyLimitIsFive() {
        Organization owned = ownedOrganization(8L, "어원환경", 42L);
        when(organizations.findOwnedForUpdate(42L)).thenReturn(Optional.of(owned));
        when(keys.countByOrganizationIdAndActiveTrue(8L)).thenReturn(5L);

        ApiException exception = assertThrows(ApiException.class,
                () -> service.issue("어원환경", "여섯번째", 60));

        assertEquals(ErrorCode.OPEN_API_ACTIVE_KEY_LIMIT, exception.errorCode());
        assertEquals(5, exception.detail().get("maximum"));
        verify(keyService, never()).issue(anyLong(), anyString(), anyInt());
    }

    @Test
    void userCannotRevokeAnotherOrganizationsKey() {
        Organization owned = ownedOrganization(8L, "어원환경", 42L);
        when(organizations.findOwnedForUpdate(42L)).thenReturn(Optional.of(owned));
        when(keys.findById(9L)).thenReturn(Optional.of(key(9L, 99L, true)));

        ApiException exception = assertThrows(ApiException.class, () -> service.revoke(9L));

        assertEquals(ErrorCode.OPEN_API_ORGANIZATION_FORBIDDEN, exception.errorCode());
        verify(keys, never()).save(any());
    }

    @Test
    void listingKeysReturnsOnlyCurrentUsersOrganization() {
        Organization owned = ownedOrganization(8L, "어원환경", 42L);
        when(organizations.findByOwnerUserId(42L)).thenReturn(Optional.of(owned));
        when(keys.findByOrganizationIdOrderByCreatedAtDesc(8L))
                .thenReturn(java.util.List.of(key(3L, 8L, true)));

        var result = service.keys();

        assertEquals(1, result.size());
        assertTrue(result.getFirst().prefix().startsWith("awon_live_"));
        verify(keys).findByOrganizationIdOrderByCreatedAtDesc(8L);
    }

    private Organization ownedOrganization(long id, String name, long userId) {
        Organization organization = Organization.ownedBy(name, userId);
        ReflectionTestUtils.setField(organization, "id", id);
        return organization;
    }

    private OrganizationApiKey key(long id, long organizationId, boolean active) {
        OrganizationApiKey key = new OrganizationApiKey(organizationId,
                "a".repeat(64), "awon_live_example", "운영 서버", 60);
        ReflectionTestUtils.setField(key, "id", id);
        if (!active) key.revoke();
        return key;
    }
}
