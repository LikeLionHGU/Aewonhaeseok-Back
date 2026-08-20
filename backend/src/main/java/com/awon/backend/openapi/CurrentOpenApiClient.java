package com.awon.backend.openapi;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
@Component
public class CurrentOpenApiClient {
    public OpenApiPrincipal principal(){
        Object value=SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        if(value instanceof OpenApiPrincipal p)return p;
        throw new IllegalStateException("Open API principal missing");
    }
}
