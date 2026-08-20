package com.awon.backend.openapi;

import com.awon.backend.auth.CurrentUser;
import com.awon.backend.common.*;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.*;
import java.util.*;

@Service
public class OpenApiAdminService {
    private final OrganizationRepository organizations;
    private final OrganizationApiKeyRepository keys;
    private final OpenApiKeyService keyService;
    private final OpenApiUsageLogRepository usage;
    private final CurrentUser currentUser;
    public OpenApiAdminService(OrganizationRepository organizations,OrganizationApiKeyRepository keys,
            OpenApiKeyService keyService,OpenApiUsageLogRepository usage,CurrentUser currentUser){
        this.organizations=organizations;this.keys=keys;this.keyService=keyService;
        this.usage=usage;this.currentUser=currentUser;
    }
    @Transactional
    public IssuedResponse createOrganization(String name,String keyName,int rpm){
        String trimmed=name.trim();
        if(organizations.existsByName(trimmed))throw new ApiException(ErrorCode.ORGANIZATION_ALREADY_EXISTS,Map.of("name",trimmed));
        try{
            Organization org=organizations.save(new Organization(trimmed,currentUser.id()));
            return issued(org,keyService.issue(org.getId(),keyName,rpm));
        }catch(DataIntegrityViolationException e){throw new ApiException(ErrorCode.ORGANIZATION_ALREADY_EXISTS,Map.of("name",trimmed));}
    }
    @Transactional(readOnly=true)
    public List<OrganizationResponse> organizations(){return organizations.findAll().stream().map(OrganizationResponse::of).toList();}
    @Transactional
    public IssuedResponse issue(long orgId,String keyName,int rpm){
        Organization org=organization(orgId);return issued(org,keyService.issue(orgId,keyName,rpm));
    }
    @Transactional(readOnly=true)
    public List<KeyResponse> keys(long orgId){organization(orgId);return keys.findByOrganizationIdOrderByCreatedAtDesc(orgId).stream().map(KeyResponse::of).toList();}
    @Transactional
    public void revoke(long orgId,long keyId){
        OrganizationApiKey key=keys.findById(keyId).filter(k->k.getOrganizationId()==orgId)
                .orElseThrow(()->new ApiException(ErrorCode.OPEN_API_KEY_INVALID));
        key.revoke();keys.save(key);
    }
    @Transactional(readOnly=true)
    public Map<String,Object> usage(long orgId){organization(orgId);return Map.of(
            "last_24_hours",usage.countRecent(orgId,OffsetDateTime.now().minusHours(24)),
            "last_30_days",usage.countRecent(orgId,OffsetDateTime.now().minusDays(30)));
    }
    private Organization organization(long id){return organizations.findById(id).orElseThrow(
            ()->new ApiException(ErrorCode.ORGANIZATION_NOT_FOUND,Map.of("id",id)));}
    private IssuedResponse issued(Organization org,OpenApiKeyService.IssuedKey issued){return new IssuedResponse(
            OrganizationResponse.of(org),KeyResponse.of(issued.entity()),issued.rawKey(),
            "이 키는 다시 조회할 수 없습니다. 안전한 비밀 저장소에 보관하세요.");}
    public record OrganizationResponse(long id,String name,boolean active,OffsetDateTime createdAt){
        static OrganizationResponse of(Organization o){return new OrganizationResponse(o.getId(),o.getName(),o.isActive(),o.getCreatedAt());}}
    public record KeyResponse(long id,String name,String prefix,boolean active,int requestsPerMinute,
                              OffsetDateTime lastUsedAt,OffsetDateTime createdAt,OffsetDateTime revokedAt){
        static KeyResponse of(OrganizationApiKey k){return new KeyResponse(k.getId(),k.getKeyName(),k.getKeyPrefix(),
                k.isActive(),k.getRequestsPerMinute(),k.getLastUsedAt(),k.getCreatedAt(),k.getRevokedAt());}}
    public record IssuedResponse(OrganizationResponse organization,KeyResponse key,String apiKey,String warning){}
}
