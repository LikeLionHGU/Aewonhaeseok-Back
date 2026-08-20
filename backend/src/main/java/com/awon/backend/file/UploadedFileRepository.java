package com.awon.backend.file;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface UploadedFileRepository extends JpaRepository<UploadedFile, Long> {

    Optional<UploadedFile> findByIdAndOwnerUserId(Long id, Long ownerUserId);
    Page<UploadedFile> findByOwnerUserId(Long ownerUserId, Pageable pageable);
    Page<UploadedFile> findByOwnerUserIdAndStatus(Long ownerUserId, FileStatus status, Pageable pageable);
}
