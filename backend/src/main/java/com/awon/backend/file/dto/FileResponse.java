package com.awon.backend.file.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.awon.backend.file.FileStatus;
import com.awon.backend.file.UploadedFile;

import java.time.OffsetDateTime;
import java.time.LocalDate;
import java.math.BigDecimal;

/**
 * 파일 단건 응답. API 명세서 B2와 같다.
 *
 * <p>Jackson이 snake_case로 직렬화하므로 originalFilename → original_filename이 된다.
 */
public record FileResponse(
        Long id,
        String filename,
        long sizeBytes,
        String contentType,
        String encodingDetected,
        Integer headerRow,
        FileStatus status,
        OffsetDateTime uploadedAt,
        Integer columnCount,
        Long pendingReviewCount,
        @JsonInclude(JsonInclude.Include.ALWAYS) LocalDate measuredFrom,
        @JsonInclude(JsonInclude.Include.ALWAYS) LocalDate measuredTo,
        String dictionaryVersion,
        BigDecimal autoMappedRate) {

    public static FileResponse of(UploadedFile file) {
        return of(file, null, null, null, null, null, null);
    }

    public static FileResponse of(UploadedFile file, Integer columnCount, Long pendingReviewCount,
                                  LocalDate measuredFrom, LocalDate measuredTo,
                                  String dictionaryVersion, BigDecimal autoMappedRate) {
        return new FileResponse(
                file.getId(),
                file.getOriginalFilename(),
                file.getSizeBytes(),
                file.getContentType(),
                file.getEncodingDetected(),
                file.getHeaderRow(),
                file.getStatus(),
                file.getUploadedAt(),
                columnCount,
                pendingReviewCount,
                measuredFrom,
                measuredTo,
                dictionaryVersion,
                autoMappedRate);
    }
}
