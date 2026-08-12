package com.awon.backend.common;

import java.util.Map;

/** 화면에 보여줄 메시지가 정해진 예외. 처리되지 않은 예외와 구분한다. */
public class ApiException extends RuntimeException {

    private final ErrorCode errorCode;
    private final Map<String, Object> detail;

    public ApiException(ErrorCode errorCode) {
        this(errorCode, Map.of());
    }

    public ApiException(ErrorCode errorCode, Map<String, Object> detail) {
        super(errorCode.message());
        this.errorCode = errorCode;
        this.detail = detail == null ? Map.of() : detail;
    }

    public ApiException(ErrorCode errorCode, Map<String, Object> detail, Throwable cause) {
        super(errorCode.message(), cause);
        this.errorCode = errorCode;
        this.detail = detail == null ? Map.of() : detail;
    }

    public ErrorCode errorCode() {
        return errorCode;
    }

    public Map<String, Object> detail() {
        return detail;
    }
}
