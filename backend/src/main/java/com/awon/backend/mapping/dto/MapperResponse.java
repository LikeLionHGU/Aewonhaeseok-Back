package com.awon.backend.mapping.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.math.BigDecimal;
import java.util.List;

/**
 * Python 매핑 서비스가 돌려주는 형태.
 *
 * <p>필드 이름은 매핑 엔진의 MappingResult·build_report()를 그대로 따른다.
 *
 * <p><b>이름을 하나하나 명시한 이유:</b> 이 DTO를 채우는 것은 스프링 MVC가 아니라
 * RestClient의 기본 JSON 변환기다. {@code spring.jackson.property-naming-strategy}가
 * 적용되지 않으므로, 명시하지 않으면 {@code dictionary_hash}가 {@code dictionaryHash}로
 * 들어가지 않고 조용히 null이 된다. 서비스 간 계약은 설정에 기대지 않는 편이 안전하다.
 */
public record MapperResponse(
        @JsonProperty("dictionary_version") String dictionaryVersion,
        @JsonProperty("dictionary_hash") String dictionaryHash,
        @JsonProperty("encoding_detected") String encodingDetected,
        @JsonProperty("header_row") Integer headerRow,
        @JsonProperty("columns") List<Col> columns) {

    /**
     * @param status exact | fuzzy_auto | needs_review | unmapped
     * @param via    body | paren | composite
     * @param score  exact일 때는 null이다
     */
    public record Col(
            @JsonProperty("column_index") Integer columnIndex,
            @JsonProperty("raw") String raw,
            @JsonProperty("normalized") String normalized,
            @JsonProperty("status") String status,
            @JsonProperty("via") String via,
            @JsonProperty("code") String code,
            @JsonProperty("candidate_code") String candidateCode,
            @JsonProperty("site") String site,
            @JsonProperty("output_column") String outputColumn,
            @JsonProperty("matched_variant") String matchedVariant,
            @JsonProperty("score") BigDecimal score,
            @JsonProperty("dict_type") String dictType,
            @JsonProperty("value_summary") ValueSummary valueSummary) {
    }

    /**
     * 컬럼의 실제 값 요약.
     *
     * <p>검증 화면에서 필수다. 인천·제주 파일의 '구분'처럼 컬럼명만으로는
     * 무엇인지 판단할 수 없는 경우가 실제로 있다 — 인천에서는 날짜,
     * 제주에서는 분기를 가리킨다.
     */
    public record ValueSummary(
            @JsonProperty("row_count") Long rowCount,
            @JsonProperty("distinct_count") Long distinctCount,
            @JsonProperty("samples") List<String> samples,
            @JsonProperty("all_unique") Boolean allUnique) {
    }
}
