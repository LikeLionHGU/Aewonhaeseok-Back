package com.awon.backend.openapi;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import java.util.HexFormat;

@Service
public class OpenApiKeyService {
    private final OrganizationApiKeyRepository keys;
    private final OrganizationRepository organizations;
    private final SecureRandom random = new SecureRandom();
    public OpenApiKeyService(OrganizationApiKeyRepository keys, OrganizationRepository organizations) {
        this.keys=keys; this.organizations=organizations;
    }
    @Transactional
    public IssuedKey issue(long orgId,String name,int rpm) {
        Organization org=organizations.findById(orgId).filter(Organization::isActive)
                .orElseThrow(() -> new com.awon.backend.common.ApiException(
                        com.awon.backend.common.ErrorCode.ORGANIZATION_NOT_FOUND,Map.of("id",orgId)));
        byte[] secret=new byte[32]; random.nextBytes(secret);
        String raw="awon_live_"+Base64.getUrlEncoder().withoutPadding().encodeToString(secret);
        String prefix=raw.substring(0,Math.min(20,raw.length()));
        OrganizationApiKey saved=keys.save(new OrganizationApiKey(org.getId(),hash(raw),prefix,name,
                Math.max(1,Math.min(10_000,rpm))));
        return new IssuedKey(saved,raw);
    }
    @Transactional(readOnly=true)
    public Optional<AuthenticatedKey> authenticate(String raw) {
        if(raw==null||!raw.startsWith("awon_live_")) return Optional.empty();
        return keys.findByKeyHashAndActiveTrue(hash(raw)).flatMap(key ->
                organizations.findById(key.getOrganizationId()).filter(Organization::isActive)
                        .map(org -> new AuthenticatedKey(key,org)));
    }
    @Transactional public void markUsed(OrganizationApiKey key){key.markUsed(); keys.save(key);}
    public String hash(String raw) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                .digest(raw.getBytes(StandardCharsets.UTF_8))); }
        catch(NoSuchAlgorithmException e){throw new IllegalStateException(e);}
    }
    public record IssuedKey(OrganizationApiKey entity,String rawKey) { }
    public record AuthenticatedKey(OrganizationApiKey key,Organization organization) { }
}
