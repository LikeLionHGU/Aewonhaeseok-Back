package com.awon.backend.mapping;

import com.awon.backend.mapping.dto.MappingResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;

/** B3 매핑. 실행은 Python 매핑 서비스에 위임하고 결과를 저장한다. */
@RestController
@RequestMapping("/api/v1/files/{fileId}/mapping")
public class MappingController {

    private final MappingService service;

    public MappingController(MappingService service) {
        this.service = service;
    }

    /**
     * 매핑 실행.
     *
     * <p>동기로 처리한다. 실측상 9MB/104만 행이 0.33초라 작업 큐를 둘 이유가 없다.
     */
    @PostMapping
    public MappingResponse run(@PathVariable Long fileId) {
        return MappingResponse.of(service.run(fileId));
    }

    /** 저장된 결과 재조회. 매핑을 다시 돌리지 않는다. */
    @GetMapping
    public MappingResponse latest(@PathVariable Long fileId) {
        return MappingResponse.of(service.latest(fileId));
    }

    /** 매핑률 전후 비교. 사전이 자란 폭을 보여주는 지표다. */
    @GetMapping("/summary")
    public SummaryResponse summary(@PathVariable Long fileId) {
        List<MappingRun> history = service.history(fileId);
        List<Round> rounds = history.stream()
                .map(r -> new Round(r.getRoundNo(), r.getDictionaryVersion(),
                        r.getAutoMappedRate(), r.getRanAt()))
                .toList();
        return new SummaryResponse(fileId, rounds, service.delta(history));
    }

    public record SummaryResponse(Long fileId, List<Round> rounds, BigDecimal delta) {
    }

    public record Round(int round, String dictionaryVersion, BigDecimal autoMappedRate,
                        OffsetDateTime ranAt) {
    }
}
