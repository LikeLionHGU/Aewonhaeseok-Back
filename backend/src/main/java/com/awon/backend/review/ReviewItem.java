package com.awon.backend.review;

import com.awon.backend.mapping.MappingColumn;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Map;

/**
 * 검증 대기열 한 줄과 그에 대한 사람 판정.
 *
 * <p><b>이 서비스의 핵심 테이블이다.</b> 사용자 판정은 여기에만 쌓는다.
 * 사전 CSV를 직접 고치면 다음 git merge에 전부 사라지기 때문이다.
 * 매핑 엔진의 apply_review()를 서버에서 호출하면 안 된다 — 그 함수가 CSV를 덮어쓴다.
 */
@Entity
@Table(name = "review_items")
public class ReviewItem {

    /** 판정 칸에 쓸 수 있는 값은 세 가지뿐이다: 승인 · 기각 · 표준코드 직접 기입. */
    public static final String VERDICT_ACCEPT = "승인";
    public static final String VERDICT_REJECT = "기각";
    public static final String VERDICT_NO_MATCH = "no_match";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "mapping_column_id", nullable = false)
    private MappingColumn mappingColumn;

    @Column(name = "file_id", nullable = false)
    private Long fileId;

    @Column(name = "raw", nullable = false, length = 500)
    private String raw;

    @Column(name = "source_column_index", nullable = false)
    private Integer sourceColumnIndex;

    @Column(name = "mapping_status", nullable = false, length = 20)
    private String mappingStatus;

    @Column(name = "candidate_code", length = 10)
    private String candidateCode;

    @Column(name = "score", precision = 4, scale = 1)
    private BigDecimal score;

    /** 실제 값 요약. 컬럼명만으로는 판단할 수 없어 반드시 함께 보여준다. */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "value_summary")
    private Map<String, Object> valueSummary;

    @Column(name = "verdict", length = 20)
    private String verdict;

    @Column(name = "verdict_note", length = 1000)
    private String verdictNote;

    /** 서버가 기록한다. 프론트가 보내지 않는다. */
    @Column(name = "reviewed_by", length = 100)
    private String reviewedBy;

    @Column(name = "reviewed_at")
    private OffsetDateTime reviewedAt;

    /** 사전 담당자에게 넘어간 시각. 같은 판정을 두 번 넘기지 않기 위한 표시. */
    @Column(name = "exported_at")
    private OffsetDateTime exportedAt;

    /**
     * 판정이 실제 사전에 반영됐는가.
     * 항상 false로 시작한다. 반영은 사전 담당자가 CLI로 하는 별도 단계다.
     */
    @Column(name = "applied_to_dictionary", nullable = false)
    private boolean appliedToDictionary = false;

    @Column(name = "created_at", nullable = false)
    private OffsetDateTime createdAt;

    protected ReviewItem() {
        // JPA
    }

    public ReviewItem(MappingColumn column, Long fileId, Map<String, Object> valueSummary) {
        this.mappingColumn = column;
        this.fileId = fileId;
        this.raw = column.getRaw();
        this.sourceColumnIndex = column.getColumnIndex();
        this.mappingStatus = column.getStatus().name();
        this.candidateCode = column.getCandidateCode();
        this.score = column.getScore();
        this.valueSummary = valueSummary;
        this.createdAt = OffsetDateTime.now();
    }

    /**
     * 사람 판정을 기록한다.
     *
     * @param verdict 승인 · 기각 · 표준코드(MD-012 등)
     */
    public void decide(String verdict, String note, String reviewer) {
        this.verdict = verdict;
        this.verdictNote = note;
        this.reviewedBy = reviewer;
        this.reviewedAt = OffsetDateTime.now();
    }

    /** 이 판정이 채택하려는 표준코드. 기각이면 null. */
    public String adoptedCode() {
        if (verdict == null || VERDICT_NO_MATCH.equals(verdict)
                || VERDICT_REJECT.equals(verdict) || "rejected".equalsIgnoreCase(verdict)) {
            return null;
        }
        if (VERDICT_ACCEPT.equals(verdict) || "approved".equalsIgnoreCase(verdict)) {
            return candidateCode;
        }
        return verdict;
    }

    public void markExported() {
        this.exportedAt = OffsetDateTime.now();
    }

    public void markAppliedToDictionary() {
        this.appliedToDictionary = true;
    }

    public boolean isPending() {
        return verdict == null;
    }

    public Long getId() {
        return id;
    }

    public MappingColumn getMappingColumn() {
        return mappingColumn;
    }

    public Long getFileId() {
        return fileId;
    }

    public String getRaw() {
        return raw;
    }

    public Integer getSourceColumnIndex() {
        return sourceColumnIndex;
    }

    public String getMappingStatus() {
        return mappingStatus;
    }

    public String getCandidateCode() {
        return candidateCode;
    }

    public BigDecimal getScore() {
        return score;
    }

    public Map<String, Object> getValueSummary() {
        return valueSummary;
    }

    public String getVerdict() {
        return verdict;
    }

    public String getVerdictNote() {
        return verdictNote;
    }

    public String getReviewedBy() {
        return reviewedBy;
    }

    public OffsetDateTime getReviewedAt() {
        return reviewedAt;
    }

    public OffsetDateTime getExportedAt() {
        return exportedAt;
    }

    public boolean isAppliedToDictionary() {
        return appliedToDictionary;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}
