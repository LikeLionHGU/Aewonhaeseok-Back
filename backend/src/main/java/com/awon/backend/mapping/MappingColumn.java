package com.awon.backend.mapping;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

import java.math.BigDecimal;

/**
 * 컬럼 하나의 판정 결과.
 *
 * <p>엔진이 준 값을 그대로 보존한다. 나중에 "왜 이렇게 판정됐나"를
 * 설명할 수 있어야 하기 때문에 매칭된 사전 표기와 판정 경로까지 남긴다.
 */
@Entity
@Table(name = "mapping_columns")
public class MappingColumn {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "mapping_run_id", nullable = false)
    private MappingRun run;

    @Column(name = "column_index", nullable = false)
    private int columnIndex;

    /**
     * 원본 컬럼명. 절대 가공하지 않는다.
     * 엑셀에서 줄바꿈된 헤더가 그대로 올 수 있다(예: "채수시각\n(WMCTM)").
     */
    @Column(name = "raw", nullable = false, length = 500)
    private String raw;

    @Column(name = "normalized", length = 500)
    private String normalized;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    private MappingStatus status;

    /** body | paren | composite. 어떤 경로로 판정했는지 */
    @Column(name = "via", length = 20)
    private String via;

    /** 자동 확정된 표준코드. needs_review·unmapped에서는 null */
    @Column(name = "code", length = 10)
    private String code;

    /** needs_review일 때의 후보. 확정이 아니다 */
    @Column(name = "candidate_code", length = 10)
    private String candidateCode;

    /** 복합 컬럼명에서 떼어낸 지점 라벨(공촌천_수온 → 공촌천) */
    @Column(name = "site", length = 200)
    private String site;

    /** 표준화된 출력 컬럼명(WQ-009@공촌천) */
    @Column(name = "output_column", length = 300)
    private String outputColumn;

    @Column(name = "matched_variant", length = 300)
    private String matchedVariant;

    /** exact는 null이다. 점수로 맞춘 게 아니기 때문 */
    @Column(name = "score", precision = 4, scale = 1)
    private BigDecimal score;

    /** 측정항목 | 메타 */
    @Column(name = "dict_type", length = 20)
    private String dictType;

    protected MappingColumn() {
        // JPA
    }

    public MappingColumn(int columnIndex, String raw, String normalized, MappingStatus status,
                         String via, String code, String candidateCode, String site,
                         String outputColumn, String matchedVariant, BigDecimal score,
                         String dictType) {
        this.columnIndex = columnIndex;
        this.raw = raw;
        this.normalized = normalized;
        this.status = status;
        this.via = via;
        this.code = code;
        this.candidateCode = candidateCode;
        this.site = site;
        this.outputColumn = outputColumn;
        this.matchedVariant = matchedVariant;
        this.score = score;
        this.dictType = dictType;
    }

    void attachTo(MappingRun run) {
        this.run = run;
    }

    /** 사람 판정을 파일 단위 override로 적용한다. 전역 사전 CSV는 건드리지 않는다. */
    public void applyReview(String adoptedCode, String standardName, String adoptedDictType) {
        this.status = MappingStatus.exact;
        this.via = "review";
        this.code = adoptedCode;
        this.candidateCode = null;
        this.matchedVariant = standardName;
        this.dictType = adoptedDictType != null ? adoptedDictType
                : (adoptedCode.startsWith("WQ-") ? "측정항목" : "메타");
        this.outputColumn = site == null || site.isBlank()
                ? adoptedCode : adoptedCode + "@" + site;
        this.score = null;
    }

    public Long getId() {
        return id;
    }

    public MappingRun getRun() {
        return run;
    }

    public int getColumnIndex() {
        return columnIndex;
    }

    public String getRaw() {
        return raw;
    }

    public String getNormalized() {
        return normalized;
    }

    public MappingStatus getStatus() {
        return status;
    }

    public String getVia() {
        return via;
    }

    public String getCode() {
        return code;
    }

    public String getCandidateCode() {
        return candidateCode;
    }

    public String getSite() {
        return site;
    }

    public String getOutputColumn() {
        return outputColumn;
    }

    public String getMatchedVariant() {
        return matchedVariant;
    }

    public BigDecimal getScore() {
        return score;
    }

    public String getDictType() {
        return dictType;
    }
}
