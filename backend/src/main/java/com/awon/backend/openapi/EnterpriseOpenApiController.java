package com.awon.backend.openapi;

import io.swagger.v3.oas.annotations.*;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.util.*;

@RestController
@RequestMapping("/open-api/v1")
@SecurityRequirement(name="apiKeyAuth")
@Tag(name="Enterprise Open API",description="기업 시스템용 수질 컬럼 표준화 API")
public class EnterpriseOpenApiController {
    private final OpenApiMappingService service;
    private final CurrentOpenApiClient client;
    public EnterpriseOpenApiController(OpenApiMappingService service,CurrentOpenApiClient client){
        this.service=service;this.client=client;
    }
    @GetMapping("/me") public Map<String,Object> me(){
        OpenApiPrincipal p=client.principal();return Map.of("organization_id",p.organizationId(),
                "organization_name",p.organizationName(),"key_name",p.keyName(),
                "requests_per_minute",p.requestsPerMinute());
    }
    @PostMapping("/mappings/columns")
    public Map<String,Object> columns(@Valid @RequestBody ColumnRequest request){
        return Map.of("items",service.mapColumns(request.columns()),"count",request.columns().size());
    }
    @PostMapping(value="/mappings/files",consumes=MediaType.MULTIPART_FORM_DATA_VALUE)
    public OpenApiMappingService.FileMapping file(@RequestPart("file") MultipartFile file){return service.mapFile(file);}
    @PostMapping("/reviews")
    public OpenApiMappingService.DictionaryTermResponse review(@Valid @RequestBody ReviewRequest request){
        return service.review(request.raw(),request.standardCode(),request.note());
    }
    @GetMapping("/dictionary/terms")
    public Map<String,Object> dictionary(){var items=service.dictionary();return Map.of("items",items,"count",items.size());}
    public record ColumnRequest(@NotEmpty @Size(max=200) List<@NotBlank @Size(max=500) String> columns){}
    public record ReviewRequest(@NotBlank @Size(max=500) String raw,
                                @NotBlank @Size(max=20) String standardCode,
                                @Size(max=1000) String note){}
}
