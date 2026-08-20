package com.awon.backend.openapi;

import jakarta.persistence.*;
import java.time.OffsetDateTime;

@Entity @Table(name = "organization_api_keys")
public class OrganizationApiKey {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @Column(name = "organization_id", nullable = false) private Long organizationId;
    @Column(name = "key_hash", nullable = false, unique = true, length = 64) private String keyHash;
    @Column(name = "key_prefix", nullable = false, length = 24) private String keyPrefix;
    @Column(name = "key_name", nullable = false, length = 100) private String keyName;
    @Column(nullable = false) private boolean active;
    @Column(name = "requests_per_minute", nullable = false) private int requestsPerMinute;
    @Column(name = "last_used_at") private OffsetDateTime lastUsedAt;
    @Column(name = "created_at", nullable = false) private OffsetDateTime createdAt;
    @Column(name = "revoked_at") private OffsetDateTime revokedAt;
    protected OrganizationApiKey() { }
    public OrganizationApiKey(long organizationId, String hash, String prefix, String name, int rpm) {
        this.organizationId=organizationId; this.keyHash=hash; this.keyPrefix=prefix;
        this.keyName=name.trim(); this.requestsPerMinute=rpm; this.active=true;
        this.createdAt=OffsetDateTime.now();
    }
    public void markUsed() { lastUsedAt = OffsetDateTime.now(); }
    public void revoke() { active=false; revokedAt=OffsetDateTime.now(); }
    public Long getId(){return id;} public Long getOrganizationId(){return organizationId;}
    public String getKeyHash(){return keyHash;} public String getKeyPrefix(){return keyPrefix;}
    public String getKeyName(){return keyName;} public boolean isActive(){return active;}
    public int getRequestsPerMinute(){return requestsPerMinute;}
    public OffsetDateTime getLastUsedAt(){return lastUsedAt;}
    public OffsetDateTime getCreatedAt(){return createdAt;} public OffsetDateTime getRevokedAt(){return revokedAt;}
}
