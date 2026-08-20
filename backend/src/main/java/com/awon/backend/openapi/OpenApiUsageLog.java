package com.awon.backend.openapi;

import jakarta.persistence.*;
import java.time.OffsetDateTime;

@Entity @Table(name="open_api_usage_logs")
public class OpenApiUsageLog {
    @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id;
    @Column(name="api_key_id",nullable=false) private Long apiKeyId;
    @Column(name="organization_id",nullable=false) private Long organizationId;
    @Column(nullable=false,length=10) private String method;
    @Column(nullable=false,length=500) private String path;
    @Column(name="response_status",nullable=false) private int responseStatus;
    @Column(name="duration_ms",nullable=false) private int durationMs;
    @Column(name="usage_units",nullable=false) private int usageUnits;
    @Column(name="requested_at",nullable=false) private OffsetDateTime requestedAt;
    protected OpenApiUsageLog() { }
    public OpenApiUsageLog(long keyId,long orgId,String method,String path,int status,int duration) {
        apiKeyId=keyId; organizationId=orgId; this.method=method; this.path=path;
        responseStatus=status; durationMs=duration; usageUnits=1; requestedAt=OffsetDateTime.now();
    }
}
