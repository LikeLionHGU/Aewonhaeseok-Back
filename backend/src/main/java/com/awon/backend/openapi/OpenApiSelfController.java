package com.awon.backend.openapi;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/open-api/keys")
public class OpenApiSelfController {
    private final OpenApiSelfService service;

    public OpenApiSelfController(OpenApiSelfService service) {
        this.service = service;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public OpenApiAdminService.IssuedResponse issue(@Valid @RequestBody IssueRequest request) {
        return service.issue(request.organizationName(), request.keyName(), request.effectiveRpm());
    }

    @GetMapping
    public List<OpenApiAdminService.KeyResponse> keys() {
        return service.keys();
    }

    @DeleteMapping("/{keyId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void revoke(@PathVariable long keyId) {
        service.revoke(keyId);
    }

    public record IssueRequest(
            @NotBlank @Size(max = 200) String organizationName,
            @NotBlank @Size(max = 100) String keyName,
            @Min(1) @Max(60)
            @Schema(description = "키별 분당 호출 한도", minimum = "1", maximum = "60", defaultValue = "60")
            Integer requestsPerMinute) {
        int effectiveRpm() {
            return requestsPerMinute == null ? 60 : requestsPerMinute;
        }
    }
}
