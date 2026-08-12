package com.awon.backend.file;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.OffsetDateTime;

/**
 * 업로드된 원본 파일.
 *
 * <p>원본 파일 자체는 디스크에 두고 여기에는 경로와 해시만 기록한다.
 * 원본은 절대 수정하지 않는다 — 감사 대응 요구사항이다.
 */
@Entity
@Table(name = "files")
public class UploadedFile {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "original_filename", nullable = false, length = 500)
    private String originalFilename;

    @Column(name = "stored_path", nullable = false, length = 1000)
    private String storedPath;

    /** SHA-256. 같은 파일을 다시 올렸는지 판별한다. */
    @Column(name = "content_hash", nullable = false, length = 64)
    private String contentHash;

    @Column(name = "size_bytes", nullable = false)
    private long sizeBytes;

    @Column(name = "content_type", length = 100)
    private String contentType;

    /** utf-8-sig | cp949 | euc-kr. 매핑 서비스가 판별해 알려준다. */
    @Column(name = "encoding_detected", length = 30)
    private String encodingDetected;

    /** 헤더가 몇 번째 행이었는지(0-based). */
    @Column(name = "header_row")
    private Integer headerRow;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    private FileStatus status = FileStatus.uploaded;

    @Column(name = "uploaded_at", nullable = false)
    private OffsetDateTime uploadedAt;

    protected UploadedFile() {
        // JPA
    }

    public UploadedFile(String originalFilename, String storedPath, String contentHash,
                        long sizeBytes, String contentType) {
        this.originalFilename = originalFilename;
        this.storedPath = storedPath;
        this.contentHash = contentHash;
        this.sizeBytes = sizeBytes;
        this.contentType = contentType;
        this.status = FileStatus.uploaded;
        this.uploadedAt = OffsetDateTime.now();
    }

    /** 매핑 결과에서 알아낸 파일 특성을 반영한다. */
    public void describeAfterMapping(String encodingDetected, Integer headerRow) {
        this.encodingDetected = encodingDetected;
        this.headerRow = headerRow;
    }

    public void markStatus(FileStatus status) {
        this.status = status;
    }

    public Long getId() {
        return id;
    }

    public String getOriginalFilename() {
        return originalFilename;
    }

    public String getStoredPath() {
        return storedPath;
    }

    public String getContentHash() {
        return contentHash;
    }

    public long getSizeBytes() {
        return sizeBytes;
    }

    public String getContentType() {
        return contentType;
    }

    public String getEncodingDetected() {
        return encodingDetected;
    }

    public Integer getHeaderRow() {
        return headerRow;
    }

    public FileStatus getStatus() {
        return status;
    }

    public OffsetDateTime getUploadedAt() {
        return uploadedAt;
    }
}
