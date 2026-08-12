package com.awon.backend.common;

import com.fasterxml.jackson.annotation.JsonInclude;

import java.util.Map;

/**
 * 모든 4xx·5xx의 공통 응답 형태. API 명세서 §1과 같다.
 *
 * <pre>
 * { "error": { "code": "...", "message": "...", "detail": { ... } } }
 * </pre>
 */
public record ApiErrorResponse(Body error) {

    @JsonInclude(JsonInclude.Include.NON_EMPTY)
    public record Body(String code, String message, Map<String, Object> detail) {
    }

    public static ApiErrorResponse of(ErrorCode code, Map<String, Object> detail) {
        return new ApiErrorResponse(new Body(code.name(), code.message(), detail));
    }

    public static ApiErrorResponse of(ErrorCode code, String message, Map<String, Object> detail) {
        return new ApiErrorResponse(new Body(code.name(), message, detail));
    }
}
