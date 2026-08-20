package com.awon.backend.openapi;
public record OpenApiPrincipal(long apiKeyId,long organizationId,String organizationName,
                               String keyName,int requestsPerMinute) { }
