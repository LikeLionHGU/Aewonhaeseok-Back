package com.awon.backend.mapping;

import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
import com.awon.backend.file.FileStatus;
import com.awon.backend.file.UploadedFile;
import com.awon.backend.file.UploadedFileRepository;
import com.awon.backend.mapping.dto.MapperResponse;
import com.awon.backend.review.ReviewItem;
import com.awon.backend.review.ReviewItemRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class MappingService {

    private final UploadedFileRepository files;
    private final MappingRunRepository runs;
    private final ReviewItemRepository reviews;
    private final MapperClient mapper;

    public MappingService(UploadedFileRepository files, MappingRunRepository runs,
                          ReviewItemRepository reviews, MapperClient mapper) {
        this.files = files;
        this.runs = runs;
        this.reviews = reviews;
        this.mapper = mapper;
    }

    /**
     * 파일 하나를 매핑하고 결과를 저장한다.
     *
     * <p>같은 파일을 다시 매핑하면 회차가 하나 늘어난다. 사전이 자란 뒤 재실행해
     * 1차와 2차의 자동 매핑률을 비교하는 것이 이 서비스의 핵심 지표다.
     */
    @Transactional
    public MappingRun run(Long fileId) {
        UploadedFile file = files.findById(fileId)
                .orElseThrow(() -> new ApiException(ErrorCode.FILE_NOT_FOUND, Map.of("id", fileId)));

        file.markStatus(FileStatus.mapping);

        Path stored = Paths.get(file.getStoredPath());
        MapperResponse response;
        try {
            response = mapper.map(stored, file.getOriginalFilename());
        } catch (ApiException e) {
            file.markStatus(FileStatus.failed);
            throw e;
        }

        int nextRound = runs.findMaxRoundNo(fileId) + 1;
        MappingRun run = new MappingRun(
                fileId,
                nextRound,
                response.dictionaryVersion(),
                response.dictionaryHash(),
                response.headerRow() == null ? 0 : response.headerRow());

        List<MapperResponse.Col> columns =
                response.columns() == null ? List.of() : response.columns();
        for (int i = 0; i < columns.size(); i++) {
            run.addColumn(toEntity(columns.get(i), i));
        }
        run.recount();
        runs.save(run);

        // 검증 대기열 생성. needs_review와 unmapped만 사람에게 넘긴다.
        for (int i = 0; i < columns.size(); i++) {
            MappingColumn column = run.getColumns().get(i);
            if (column.getStatus().needsHuman()) {
                reviews.save(new ReviewItem(column, fileId, toMap(columns.get(i).valueSummary())));
            }
        }

        file.describeAfterMapping(response.encodingDetected(), run.getHeaderRow());
        file.markStatus(run.hasPendingReview() ? FileStatus.reviewing : FileStatus.completed);

        return run;
    }

    /** 저장된 결과를 컬럼까지 채워서 돌려준다. 응답을 만들 때는 이걸 쓴다. */
    @Transactional(readOnly = true)
    public MappingRun latest(Long fileId) {
        return runs.findLatestWithColumns(fileId)
                .orElseThrow(() -> new ApiException(ErrorCode.MAPPING_NOT_FOUND,
                        Map.of("file_id", fileId)));
    }

    @Transactional(readOnly = true)
    public List<MappingRun> history(Long fileId) {
        return runs.findByFileIdOrderByRoundNoAsc(fileId);
    }

    private MappingColumn toEntity(MapperResponse.Col col, int fallbackIndex) {
        MappingStatus status = parseStatus(col.status());
        return new MappingColumn(
                col.columnIndex() == null ? fallbackIndex : col.columnIndex(),
                col.raw(),
                col.normalized(),
                status,
                col.via(),
                // 자동 확정일 때만 code를 채운다. 후보를 확정처럼 저장하면 안 된다.
                status.isAuto() ? col.code() : null,
                status.isAuto() ? null : col.candidateCode(),
                col.site(),
                col.outputColumn(),
                col.matchedVariant(),
                // exact는 점수가 없다. 엔진이 null을 주는 것이 정상이다.
                col.score() == null ? null : col.score().setScale(1, java.math.RoundingMode.HALF_UP),
                col.dictType());
    }

    private MappingStatus parseStatus(String raw) {
        try {
            return MappingStatus.valueOf(raw);
        } catch (IllegalArgumentException | NullPointerException e) {
            // 엔진이 모르는 status를 주면 조용히 자동 확정으로 취급하지 않는다.
            // 틀린 매핑이 소리 없이 섞이는 것이 가장 위험하다.
            return MappingStatus.unmapped;
        }
    }

    private Map<String, Object> toMap(MapperResponse.ValueSummary summary) {
        if (summary == null) {
            return null;
        }
        Map<String, Object> map = new HashMap<>();
        map.put("row_count", summary.rowCount());
        map.put("distinct_count", summary.distinctCount());
        map.put("samples", summary.samples());
        map.put("all_unique", summary.allUnique());
        return map;
    }

    /** 전후 비교의 상승폭. 1차와 마지막 회차의 차이다. */
    public BigDecimal delta(List<MappingRun> history) {
        if (history.size() < 2) {
            return BigDecimal.ZERO.setScale(1);
        }
        BigDecimal first = history.get(0).getAutoMappedRate();
        BigDecimal last = history.get(history.size() - 1).getAutoMappedRate();
        return last.subtract(first).setScale(1, java.math.RoundingMode.HALF_UP);
    }
}
