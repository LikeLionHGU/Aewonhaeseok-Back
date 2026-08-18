package com.awon.backend.file;

import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
import com.awon.backend.file.dto.FileResponse;
import com.awon.backend.mapping.MappingRun;
import com.awon.backend.mapping.MappingRunRepository;
import com.awon.backend.review.ReviewItemRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;
import java.util.Optional;

@Service
public class FileService {

    private final UploadedFileRepository files;
    private final MappingRunRepository runs;
    private final ReviewItemRepository reviews;
    private final FileStorage storage;
    private final JdbcTemplate jdbc;

    public FileService(UploadedFileRepository files, MappingRunRepository runs,
                       ReviewItemRepository reviews, FileStorage storage, JdbcTemplate jdbc) {
        this.files = files;
        this.runs = runs;
        this.reviews = reviews;
        this.storage = storage;
        this.jdbc = jdbc;
    }

    @Transactional
    public UploadedFile upload(MultipartFile multipart) {
        FileStorage.Stored stored = storage.store(multipart);
        UploadedFile file = new UploadedFile(
                multipart.getOriginalFilename(),
                stored.path().toString(),
                stored.sha256(),
                stored.sizeBytes(),
                multipart.getContentType());
        return files.save(file);
    }

    @Transactional(readOnly = true)
    public UploadedFile get(Long id) {
        return files.findById(id)
                .orElseThrow(() -> new ApiException(ErrorCode.FILE_NOT_FOUND, Map.of("id", id)));
    }

    @Transactional(readOnly = true)
    public Page<UploadedFile> list(FileStatus status, Pageable pageable) {
        return status == null ? files.findAll(pageable) : files.findByStatus(status, pageable);
    }

    /**
     * 목록 항목 하나를 화면용으로 만든다.
     *
     * <p>pendingReviewCount는 화면의 "확인 필요 N건" 배지에 그대로 쓰인다.
     */
    @Transactional(readOnly = true)
    public FileResponse describe(UploadedFile file) {
        Optional<MappingRun> latest = runs.findFirstByFileIdOrderByRoundNoDesc(file.getId());
        Integer columnCount = latest.map(MappingRun::getTotalColumns).orElse(null);
        long pending = reviews.countByFileIdAndVerdictIsNull(file.getId());
        java.util.Map<String, Object> period = jdbc.queryForMap("""
                SELECT MIN(measured_on) AS measured_from, MAX(measured_on) AS measured_to
                  FROM measurements WHERE file_id = ?
                """, file.getId());
        return FileResponse.of(
                file,
                columnCount,
                pending,
                toLocalDate(period.get("measured_from")),
                toLocalDate(period.get("measured_to")),
                latest.map(MappingRun::getDictionaryVersion).orElse(null),
                latest.map(MappingRun::getAutoMappedRate).orElse(null));
    }

    private java.time.LocalDate toLocalDate(Object value) {
        if (value instanceof java.sql.Date date) {
            return date.toLocalDate();
        }
        if (value instanceof java.time.LocalDate date) {
            return date;
        }
        return null;
    }
}
