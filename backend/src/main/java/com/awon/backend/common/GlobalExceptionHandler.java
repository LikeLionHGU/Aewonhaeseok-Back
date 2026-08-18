package com.awon.backend.common;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.multipart.support.MissingServletRequestPartException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.HashMap;
import java.util.Map;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(ApiException.class)
    public ResponseEntity<ApiErrorResponse> handleApi(ApiException e) {
        // 5xx만 스택트레이스를 남긴다. 4xx는 사용자 입력 문제라 소음이 된다.
        if (e.errorCode().status().is5xxServerError()) {
            log.error("{} - {}", e.errorCode().name(), e.getMessage(), e);
        } else {
            log.debug("{} - {}", e.errorCode().name(), e.getMessage());
        }
        return ResponseEntity.status(e.errorCode().status())
                .body(ApiErrorResponse.of(e.errorCode(), e.detail()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiErrorResponse> handleValidation(MethodArgumentNotValidException e) {
        Map<String, Object> fields = new HashMap<>();
        e.getBindingResult().getFieldErrors()
                .forEach(f -> fields.put(f.getField(), f.getDefaultMessage()));
        return ResponseEntity.badRequest().body(new ApiErrorResponse(
                new ApiErrorResponse.Body("VALIDATION_FAILED", "입력값을 확인해 주세요.", fields)));
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<ApiErrorResponse> handleTooLarge(MaxUploadSizeExceededException e) {
        return ResponseEntity.status(413).body(new ApiErrorResponse(
                new ApiErrorResponse.Body("FILE_TOO_LARGE", "파일이 너무 큽니다.", Map.of())));
    }

    @ExceptionHandler(HttpMediaTypeNotSupportedException.class)
    public ResponseEntity<ApiErrorResponse> handleUnsupportedMedia(HttpMediaTypeNotSupportedException e) {
        return ResponseEntity.status(415).body(new ApiErrorResponse(
                new ApiErrorResponse.Body("CONTENT_TYPE_UNSUPPORTED",
                        "요청 Content-Type이 올바르지 않습니다.",
                        Map.of("content_type", String.valueOf(e.getContentType())))));
    }

    @ExceptionHandler({HttpMessageNotReadableException.class,
            MissingServletRequestPartException.class,
            MissingServletRequestParameterException.class,
            MethodArgumentTypeMismatchException.class})
    public ResponseEntity<ApiErrorResponse> handleBadRequest(Exception e) {
        return ResponseEntity.badRequest().body(new ApiErrorResponse(
                new ApiErrorResponse.Body("REQUEST_INVALID",
                        "요청 형식이나 입력값을 확인해 주세요.", Map.of())));
    }

    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<ApiErrorResponse> handleNotFound(NoResourceFoundException e) {
        return ResponseEntity.status(404).body(new ApiErrorResponse(
                new ApiErrorResponse.Body("RESOURCE_NOT_FOUND",
                        "요청한 API 경로를 찾을 수 없습니다.", Map.of())));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiErrorResponse> handleUnexpected(Exception e) {
        log.error("처리되지 않은 예외", e);
        return ResponseEntity.internalServerError().body(new ApiErrorResponse(
                new ApiErrorResponse.Body("INTERNAL_ERROR", "서버 오류가 발생했습니다.", Map.of())));
    }
}
