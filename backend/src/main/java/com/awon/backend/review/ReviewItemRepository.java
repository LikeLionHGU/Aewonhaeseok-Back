package com.awon.backend.review;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;

public interface ReviewItemRepository extends JpaRepository<ReviewItem, Long> {

    /** 아직 판정되지 않은 것. 검증 화면의 기본 목록이다. */
    Page<ReviewItem> findByFileIdAndVerdictIsNull(Long fileId, Pageable pageable);

    Page<ReviewItem> findByVerdictIsNull(Pageable pageable);

    Page<ReviewItem> findByFileId(Long fileId, Pageable pageable);

    @Query("select r from ReviewItem r, UploadedFile f where r.fileId = f.id and f.ownerUserId = :ownerId and r.verdict is null")
    Page<ReviewItem> findOwnedPending(Long ownerId, Pageable pageable);

    @Query("select r from ReviewItem r, UploadedFile f where r.fileId = f.id and f.ownerUserId = :ownerId")
    Page<ReviewItem> findOwned(Long ownerId, Pageable pageable);

    @Query("select r from ReviewItem r, UploadedFile f where r.fileId = f.id and f.ownerUserId = :ownerId and r.fileId = :fileId and r.verdict is null")
    Page<ReviewItem> findOwnedPendingByFile(Long ownerId, Long fileId, Pageable pageable);

    @Query("select r from ReviewItem r, UploadedFile f where r.fileId = f.id and f.ownerUserId = :ownerId and r.fileId = :fileId")
    Page<ReviewItem> findOwnedByFile(Long ownerId, Long fileId, Pageable pageable);

    @Query("select r from ReviewItem r, UploadedFile f where r.fileId = f.id and f.ownerUserId = :ownerId and r.id = :id")
    Optional<ReviewItem> findOwnedById(Long ownerId, Long id);

    long countByFileIdAndVerdictIsNull(Long fileId);

    List<ReviewItem> findByFileIdOrderByCreatedAtDesc(Long fileId);

    /**
     * 사전 담당자에게 아직 안 넘긴 판정.
     * tools/export_judgments.py가 가져갈 목록이다.
     */
    @Query("""
            select r from ReviewItem r
            where r.verdict is not null
              and r.verdict <> '기각'
              and r.exportedAt is null
            order by r.reviewedAt asc
            """)
    List<ReviewItem> findUnexportedVerdicts();
}
