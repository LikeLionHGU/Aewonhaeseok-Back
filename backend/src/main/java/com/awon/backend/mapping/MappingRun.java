package com.awon.backend.mapping;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.Table;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 매핑 실행 1회.
 *
 * <p>같은 파일을 사전이 자란 뒤 다시 돌리면 round_no가 하나 늘어난 행이 생긴다.
 * 1차와 2차의 자동 매핑률 차이가 "사전이 자란다"를 보여주는 지표다.
 */
@Entity
@Table(name = "mapping_runs")
public class MappingRun {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "file_id", nullable = false)
    private Long fileId;

    @Column(name = "round_no", nullable = false)
    private int roundNo;

    /** 어떤 사전으로 매핑한 결과인지. 나중에도 추적할 수 있어야 한다. */
    @Column(name = "dictionary_version", nullable = false, length = 40)
    private String dictionaryVersion;

    /** 같은 날 사전을 두 번 고쳐도 달라진다. 버전 이름만으로는 부족하다. */
    @Column(name = "dictionary_hash", nullable = false, length = 40)
    private String dictionaryHash;

    @Column(name = "header_row", nullable = false)
    private int headerRow;

    @Column(name = "total_columns", nullable = false)
    private int totalColumns;

    @Column(name = "auto_mapped", nullable = false)
    private int autoMapped;

    @Column(name = "needs_review", nullable = false)
    private int needsReview;

    @Column(name = "unmapped", nullable = false)
    private int unmapped;

    @Column(name = "auto_mapped_rate", nullable = false, precision = 5, scale = 1)
    private BigDecimal autoMappedRate;

    @Column(name = "ran_at", nullable = false)
    private OffsetDateTime ranAt;

    @OneToMany(mappedBy = "run", cascade = CascadeType.ALL, orphanRemoval = true,
            fetch = FetchType.LAZY)
    @OrderBy("columnIndex ASC")
    private List<MappingColumn> columns = new ArrayList<>();

    protected MappingRun() {
        // JPA
    }

    public MappingRun(Long fileId, int roundNo, String dictionaryVersion, String dictionaryHash,
                      int headerRow) {
        this.fileId = fileId;
        this.roundNo = roundNo;
        this.dictionaryVersion = dictionaryVersion;
        this.dictionaryHash = dictionaryHash;
        this.headerRow = headerRow;
        this.ranAt = OffsetDateTime.now();
        this.autoMappedRate = BigDecimal.ZERO;
    }

    public void addColumn(MappingColumn column) {
        column.attachTo(this);
        columns.add(column);
    }

    /**
     * 컬럼을 다 채운 뒤 집계한다.
     *
     * <p>비율은 파이썬이 준 값을 그대로 믿지 않고 여기서 다시 센다.
     * 두 곳에서 계산하면 언젠가 어긋나는데, 화면에 뜨는 건 이 값이다.
     */
    public void recount() {
        this.totalColumns = columns.size();
        this.autoMapped = (int) columns.stream().filter(c -> c.getStatus().isAuto()).count();
        this.needsReview = (int) columns.stream()
                .filter(c -> c.getStatus() == MappingStatus.needs_review).count();
        this.unmapped = (int) columns.stream()
                .filter(c -> c.getStatus() == MappingStatus.unmapped).count();
        this.autoMappedRate = ratio(autoMapped, totalColumns);
    }

    private BigDecimal ratio(int part, int whole) {
        if (whole == 0) {
            return BigDecimal.ZERO.setScale(1);
        }
        return BigDecimal.valueOf(100.0 * part / whole).setScale(1, java.math.RoundingMode.HALF_UP);
    }

    public boolean hasPendingReview() {
        return needsReview + unmapped > 0;
    }

    public Long getId() {
        return id;
    }

    public Long getFileId() {
        return fileId;
    }

    public int getRoundNo() {
        return roundNo;
    }

    public String getDictionaryVersion() {
        return dictionaryVersion;
    }

    public String getDictionaryHash() {
        return dictionaryHash;
    }

    public int getHeaderRow() {
        return headerRow;
    }

    public int getTotalColumns() {
        return totalColumns;
    }

    public int getAutoMapped() {
        return autoMapped;
    }

    public int getNeedsReview() {
        return needsReview;
    }

    public int getUnmapped() {
        return unmapped;
    }

    public BigDecimal getAutoMappedRate() {
        return autoMappedRate;
    }

    public OffsetDateTime getRanAt() {
        return ranAt;
    }

    public List<MappingColumn> getColumns() {
        return columns;
    }
}
