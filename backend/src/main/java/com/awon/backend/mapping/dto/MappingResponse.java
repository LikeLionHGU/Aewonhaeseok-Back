package com.awon.backend.mapping.dto;

import com.awon.backend.mapping.MappingColumn;
import com.awon.backend.mapping.MappingRun;

import java.math.BigDecimal;
import java.util.List;

/** 매핑 결과 응답. API 명세서 B3과 같다. */
public record MappingResponse(
        Long fileId,
        int roundNo,
        int headerRow,
        String dictionaryVersion,
        Summary summary,
        List<Col> columns) {

    public record Summary(
            int totalColumns,
            int autoMapped,
            int needsReview,
            int unmapped,
            BigDecimal autoMappedRate,
            BigDecimal needsReviewRate,
            BigDecimal unmappedRate) {
    }

    public record Col(
            String raw,
            String normalized,
            String status,
            String via,
            String code,
            String candidateCode,
            String site,
            String outputColumn,
            String matchedVariant,
            BigDecimal score,
            String dictType) {
    }

    public static MappingResponse of(MappingRun run) {
        int total = run.getTotalColumns();
        return new MappingResponse(
                run.getFileId(),
                run.getRoundNo(),
                run.getHeaderRow(),
                run.getDictionaryVersion(),
                new Summary(
                        total,
                        run.getAutoMapped(),
                        run.getNeedsReview(),
                        run.getUnmapped(),
                        run.getAutoMappedRate(),
                        rate(run.getNeedsReview(), total),
                        rate(run.getUnmapped(), total)),
                run.getColumns().stream().map(MappingResponse::col).toList());
    }

    private static Col col(MappingColumn c) {
        return new Col(
                c.getRaw(),
                c.getNormalized(),
                c.getStatus().name(),
                c.getVia(),
                c.getCode(),
                c.getCandidateCode(),
                c.getSite(),
                c.getOutputColumn(),
                c.getMatchedVariant(),
                c.getScore(),
                c.getDictType());
    }

    private static BigDecimal rate(int part, int whole) {
        if (whole == 0) {
            return BigDecimal.ZERO.setScale(1);
        }
        return BigDecimal.valueOf(100.0 * part / whole)
                .setScale(1, java.math.RoundingMode.HALF_UP);
    }
}
