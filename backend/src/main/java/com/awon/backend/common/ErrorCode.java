package com.awon.backend.common;

import org.springframework.http.HttpStatus;

/**
 * API 명세서 §1의 에러 코드 표.
 *
 * <p>message는 화면에 그대로 띄울 수 있는 한국어 문장으로 둔다.
 * 프론트가 문구를 새로 만들지 않아도 되게 하기 위함이다.
 */
public enum ErrorCode {

    FILE_FORMAT_UNSUPPORTED(HttpStatus.BAD_REQUEST,
            "지원하지 않는 파일 형식입니다. 엑셀(xlsx, xls, xlsm) 또는 CSV만 올릴 수 있습니다."),

    FILE_ENCODING_UNSUPPORTED(HttpStatus.BAD_REQUEST,
            "CSV 인코딩을 인식하지 못했습니다. 파일을 UTF-8로 저장한 뒤 다시 시도해 주세요."),

    FILE_EMPTY(HttpStatus.BAD_REQUEST,
            "빈 파일입니다."),

    FILE_NOT_FOUND(HttpStatus.NOT_FOUND,
            "파일을 찾을 수 없습니다."),

    FILE_STORAGE_FAILED(HttpStatus.INTERNAL_SERVER_ERROR,
            "파일을 저장하지 못했습니다."),

    MAPPING_NOT_FOUND(HttpStatus.NOT_FOUND,
            "매핑 결과가 없습니다. 먼저 매핑을 실행해 주세요."),

    MAPPING_ALREADY_RUNNING(HttpStatus.CONFLICT,
            "이미 매핑이 진행 중입니다."),

    REVIEW_NOT_FOUND(HttpStatus.NOT_FOUND,
            "검증 항목을 찾을 수 없습니다."),

    VERDICT_REQUIRED(HttpStatus.BAD_REQUEST,
            "판정 값이 비어 있습니다. 맞음·아님 중 하나를 고르거나 표준코드를 직접 입력해 주세요."),

    VERDICT_CANDIDATE_MISSING(HttpStatus.UNPROCESSABLE_CONTENT,
            "후보 표준코드가 없어 '승인'으로 판정할 수 없습니다. 표준코드를 직접 골라 주세요."),

    VERDICT_CODE_UNKNOWN(HttpStatus.UNPROCESSABLE_CONTENT,
            "사전에 없는 표준코드입니다."),

    ANALYSIS_NOT_FOUND(HttpStatus.NOT_FOUND,
            "분석 기록을 찾을 수 없습니다."),

    MAPPER_UNAVAILABLE(HttpStatus.SERVICE_UNAVAILABLE,
            "매핑 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요."),

    MAPPER_FAILED(HttpStatus.BAD_GATEWAY,
            "매핑 중 오류가 발생했습니다."),

    DICTIONARY_CONFLICT(HttpStatus.INTERNAL_SERVER_ERROR,
            "표준 사전에 표기 충돌이 있습니다. 사전을 먼저 정리해야 합니다.");

    private final HttpStatus status;
    private final String message;

    ErrorCode(HttpStatus status, String message) {
        this.status = status;
        this.message = message;
    }

    public HttpStatus status() {
        return status;
    }

    public String message() {
        return message;
    }
}
