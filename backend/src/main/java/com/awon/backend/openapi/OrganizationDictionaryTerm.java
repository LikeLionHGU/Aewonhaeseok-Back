package com.awon.backend.openapi;

import jakarta.persistence.*;
import java.time.OffsetDateTime;

@Entity @Table(name = "organization_dictionary_terms")
public class OrganizationDictionaryTerm {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @Column(name="organization_id", nullable=false) private Long organizationId;
    @Column(name="alias_raw", nullable=false, length=500) private String aliasRaw;
    @Column(name="alias_normalized", nullable=false, length=500) private String aliasNormalized;
    @Column(name="standard_code", nullable=false, length=20) private String standardCode;
    @Column(length=1000) private String note;
    @Column(name="created_at", nullable=false) private OffsetDateTime createdAt;
    @Column(name="updated_at", nullable=false) private OffsetDateTime updatedAt;
    protected OrganizationDictionaryTerm() { }
    public OrganizationDictionaryTerm(long orgId, String raw, String normalized, String code, String note) {
        organizationId=orgId; aliasRaw=raw; aliasNormalized=normalized; standardCode=code; this.note=note;
        createdAt=OffsetDateTime.now(); updatedAt=createdAt;
    }
    public void update(String raw, String code, String note) {
        aliasRaw=raw; standardCode=code; this.note=note; updatedAt=OffsetDateTime.now();
    }
    public Long getId(){return id;} public Long getOrganizationId(){return organizationId;}
    public String getAliasRaw(){return aliasRaw;} public String getAliasNormalized(){return aliasNormalized;}
    public String getStandardCode(){return standardCode;} public String getNote(){return note;}
    public OffsetDateTime getCreatedAt(){return createdAt;} public OffsetDateTime getUpdatedAt(){return updatedAt;}
}
