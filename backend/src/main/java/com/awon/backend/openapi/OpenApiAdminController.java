package com.awon.backend.openapi;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@RestController
@RequestMapping("/api/v1/admin/open-api")
public class OpenApiAdminController {
    private final OpenApiAdminService service;
    public OpenApiAdminController(OpenApiAdminService service){this.service=service;}
    @PostMapping("/organizations") @ResponseStatus(HttpStatus.CREATED)
    public OpenApiAdminService.IssuedResponse create(@Valid @RequestBody CreateOrganizationRequest r){
        return service.createOrganization(r.name(),r.keyName(),r.effectiveRpm());}
    @GetMapping("/organizations") public List<OpenApiAdminService.OrganizationResponse> organizations(){return service.organizations();}
    @PostMapping("/organizations/{orgId}/keys") @ResponseStatus(HttpStatus.CREATED)
    public OpenApiAdminService.IssuedResponse issue(@PathVariable long orgId,@Valid @RequestBody IssueKeyRequest r){
        return service.issue(orgId,r.keyName(),r.effectiveRpm());}
    @GetMapping("/organizations/{orgId}/keys") public List<OpenApiAdminService.KeyResponse> keys(@PathVariable long orgId){return service.keys(orgId);}
    @DeleteMapping("/organizations/{orgId}/keys/{keyId}") @ResponseStatus(HttpStatus.NO_CONTENT)
    public void revoke(@PathVariable long orgId,@PathVariable long keyId){service.revoke(orgId,keyId);}
    @GetMapping("/organizations/{orgId}/usage") public Map<String,Object> usage(@PathVariable long orgId){return service.usage(orgId);}
    public record CreateOrganizationRequest(@NotBlank @Size(max=200) String name,
            @NotBlank @Size(max=100) String keyName,
            @Min(1) @Max(10000) Integer requestsPerMinute){int effectiveRpm(){return requestsPerMinute==null?60:requestsPerMinute;}}
    public record IssueKeyRequest(@NotBlank @Size(max=100) String keyName,
            @Min(1) @Max(10000) Integer requestsPerMinute){int effectiveRpm(){return requestsPerMinute==null?60:requestsPerMinute;}}
}
