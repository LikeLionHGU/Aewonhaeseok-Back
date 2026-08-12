package com.awon.backend.analysis;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.LocalDate;
import java.util.List;

/**
 * 분석 조건.
 *
 * <p><b>사용자가 SQL을 보내지 않는다.</b> 조건만 보내고 서버가 SQL을 조립한다.
 * 그래서 주입 위험이 구조적으로 없다 — 값은 전부 바인딩 파라미터로 들어가고,
 * 집계 단위나 지표처럼 SQL 문법에 섞이는 것은 열거형으로 제한된다.
 *
 * <p>자연어 파싱(B7 후반)이 붙으면, 파서가 문장을 이 객체로 바꿔 주고
 * 실행 경로는 지금과 똑같이 흐른다. 파서가 틀려도 임의의 SQL이 돌지는 않는다.
 */
public record AnalysisRequest(
        @JsonProperty("site_names") List<String> siteNames,
        @JsonProperty("outlets") List<String> outlets,
        @JsonProperty("item_codes") List<String> itemCodes,
        @JsonProperty("sample_type") String sampleType,
        @JsonProperty("from") LocalDate from,
        @JsonProperty("to") LocalDate to,
        @JsonProperty("bucket") Bucket bucket,
        @JsonProperty("metric") Metric metric,
        @JsonProperty("standard_set") String standardSet,
        @JsonProperty("region_grade") String regionGrade) {

    /** 집계 단위. SQL 조각과 1:1로 대응하며 이 목록 밖의 값은 들어올 수 없다. */
    public enum Bucket {
        month("DATE_FORMAT(m.measured_on, '%Y-%m')"),
        quarter("CONCAT(YEAR(m.measured_on), '-Q', QUARTER(m.measured_on))"),
        year("CAST(YEAR(m.measured_on) AS CHAR)"),
        /** 집계하지 않고 원자료를 그대로 본다 */
        none("CAST(m.measured_on AS CHAR)");

        private final String expression;

        Bucket(String expression) {
            this.expression = expression;
        }

        public String expression() {
            return expression;
        }
    }

    /** 집계 지표. 마찬가지로 열거형이라 임의 함수가 들어올 수 없다. */
    public enum Metric {
        avg("AVG(m.value_num)"),
        max("MAX(m.value_num)"),
        min("MIN(m.value_num)"),
        count("COUNT(m.value_num)");

        private final String expression;

        Metric(String expression) {
            this.expression = expression;
        }

        public String expression() {
            return expression;
        }
    }

    /**
     * 지정되지 않은 조건에 기본값을 채운다.
     *
     * <p>기능명세서의 조건 확인 화면이 "추측하지 않고 사람에게 확인받는 구조"인 이유가
     * 여기 있다. 기간을 안 고르면 전체가 되는데, 그게 사용자가 원한 것인지는 알 수 없다.
     * 그래서 서버는 기본값을 채우되 응답에 무엇을 채웠는지 함께 알려준다.
     */
    public AnalysisRequest withDefaults() {
        return new AnalysisRequest(
                siteNames == null ? List.of() : siteNames,
                outlets == null ? List.of() : outlets,
                itemCodes == null ? List.of() : itemCodes,
                sampleType,
                from,
                to,
                bucket == null ? Bucket.month : bucket,
                metric == null ? Metric.avg : metric,
                standardSet == null ? "배출허용기준" : standardSet,
                regionGrade);
    }

    /** 사용자가 지정하지 않아 서버가 채운 항목. 화면이 "이렇게 해석했습니다"를 보여주는 데 쓴다. */
    public List<String> assumptions() {
        List<String> assumed = new java.util.ArrayList<>();
        if (bucket == null) {
            assumed.add("집계 단위를 월별로 두었습니다");
        }
        if (metric == null) {
            assumed.add("지표를 평균으로 두었습니다");
        }
        if (from == null && to == null) {
            assumed.add("기간을 전체로 두었습니다");
        }
        if (regionGrade == null) {
            assumed.add("지역구분을 지정하지 않아 기준선을 표시하지 않습니다");
        }
        return assumed;
    }
}
