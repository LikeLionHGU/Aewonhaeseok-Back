package com.awon.backend.openapi;

import com.awon.backend.auth.CurrentUser;
import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;

@Service
public class OpenApiSelfService {
    static final int MAX_ACTIVE_KEYS = 5;

    private final OrganizationRepository organizations;
    private final OrganizationApiKeyRepository keys;
    private final OpenApiKeyService keyService;
    private final CurrentUser currentUser;

    public OpenApiSelfService(OrganizationRepository organizations,
                              OrganizationApiKeyRepository keys,
                              OpenApiKeyService keyService,
                              CurrentUser currentUser) {
        this.organizations = organizations;
        this.keys = keys;
        this.keyService = keyService;
        this.currentUser = currentUser;
    }

    @Transactional
    public OpenApiAdminService.IssuedResponse issue(String organizationName, String keyName, int rpm) {
        long userId = currentUser.id();
        String requestedName = organizationName.trim();
        Organization organization = organizations.findOwnedForUpdate(userId)
                .map(existing -> requireMatchingOrganization(existing, requestedName))
                .orElseGet(() -> createOwnedOrganization(requestedName, userId));

        long activeKeys = keys.countByOrganizationIdAndActiveTrue(organization.getId());
        if (activeKeys >= MAX_ACTIVE_KEYS) {
            throw new ApiException(ErrorCode.OPEN_API_ACTIVE_KEY_LIMIT,
                    Map.of("maximum", MAX_ACTIVE_KEYS, "active_keys", activeKeys));
        }

        OpenApiKeyService.IssuedKey issued = keyService.issue(organization.getId(), keyName, rpm);
        return new OpenApiAdminService.IssuedResponse(
                OpenApiAdminService.OrganizationResponse.of(organization),
                OpenApiAdminService.KeyResponse.of(issued.entity()),
                issued.rawKey(),
                "이 키는 다시 조회할 수 없습니다. 안전한 비밀 저장소에 보관하세요.");
    }

    @Transactional(readOnly = true)
    public List<OpenApiAdminService.KeyResponse> keys() {
        return organizations.findByOwnerUserId(currentUser.id())
                .map(organization -> keys.findByOrganizationIdOrderByCreatedAtDesc(organization.getId())
                        .stream().map(OpenApiAdminService.KeyResponse::of).toList())
                .orElseGet(List::of);
    }

    @Transactional
    public void revoke(long keyId) {
        Organization organization = organizations.findOwnedForUpdate(currentUser.id())
                .orElseThrow(() -> forbidden(keyId));
        OrganizationApiKey key = keys.findById(keyId)
                .filter(candidate -> candidate.getOrganizationId().equals(organization.getId()))
                .orElseThrow(() -> forbidden(keyId));
        if (key.isActive()) {
            key.revoke();
            keys.save(key);
        }
    }

    private Organization requireMatchingOrganization(Organization organization, String requestedName) {
        if (!organization.getName().equals(requestedName)) {
            throw new ApiException(ErrorCode.OPEN_API_ORGANIZATION_FORBIDDEN,
                    Map.of("organization_name", requestedName));
        }
        return organization;
    }

    private Organization createOwnedOrganization(String name, long userId) {
        if (organizations.existsByName(name)) {
            throw new ApiException(ErrorCode.OPEN_API_ORGANIZATION_FORBIDDEN,
                    Map.of("organization_name", name));
        }
        try {
            return organizations.save(Organization.ownedBy(name, userId));
        } catch (DataIntegrityViolationException exception) {
            throw new ApiException(ErrorCode.OPEN_API_ORGANIZATION_FORBIDDEN,
                    Map.of("organization_name", name), exception);
        }
    }

    private ApiException forbidden(long keyId) {
        return new ApiException(ErrorCode.OPEN_API_ORGANIZATION_FORBIDDEN, Map.of("key_id", keyId));
    }
}
