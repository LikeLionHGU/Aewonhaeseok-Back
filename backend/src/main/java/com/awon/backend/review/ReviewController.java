package com.awon.backend.review;

import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
import com.awon.backend.common.PageResponse;
import com.awon.backend.dictionary.TermNameCache;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Map;

/** B4 용어 검증. */
@RestController
@RequestMapping("/api/v1/reviews")
public class ReviewController {

    private final ReviewService service;
    private final TermNameCache terms;

    public ReviewController(ReviewService service, TermNameCache terms) {
        this.service = service;
        this.terms = terms;
    }

    /**
     * 검증 대기열.
     *
     * <p>needs_review와 unmapped만 나온다. 컬럼명만으로는 판단이 불가능하므로
     * 실제 값 요약을 함께 준다.
     */
    @GetMapping
    public PageResponse<ReviewResponse> list(
            @RequestParam(name = "file_id", required = false) Long fileId,
            @RequestParam(defaultValue = "pending") String status,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {

        PageRequest pageable = PageRequest.of(
                Math.max(0, page - 1), size, Sort.by(Sort.Direction.ASC, "id"));
        return PageResponse.from(service.list(fileId, status, pageable),
                item -> ReviewResponse.of(item, terms.nameOf(item.getCandidateCode())));
    }

    /**
     * 판정 저장.
     *
     * <p>판정자와 판정 시각은 서버가 기록한다. 프론트가 보내지 않는다.
     */
    @PostMapping("/{id}/verdict")
    public ReviewResponse decide(@PathVariable Long id, @Valid @RequestBody VerdictRequest request) {
        // TODO 인증 붙기 전까지는 임시 판정자. B1 결정(판정자 신원)이 나오면 교체한다.
        ReviewItem decided = service.decide(id, request.verdict(), request.note(), "미상");
        return ReviewResponse.of(decided, terms.nameOf(decided.getCandidateCode()));
    }

    public record VerdictRequest(
            @NotBlank(message = "판정 값이 비어 있습니다.") String verdict,
            String note) {
    }

    public record ReviewResponse(
            Long id,
            Long fileId,
            String raw,
            String mappingStatus,
            String candidateCode,
            String candidateName,
            BigDecimal score,
            Map<String, Object> valueSummary,
            String verdict,
            String reviewedBy,
            OffsetDateTime reviewedAt,
            boolean appliedToDictionary) {

        static ReviewResponse of(ReviewItem item, String candidateName) {
            return new ReviewResponse(
                    item.getId(),
                    item.getFileId(),
                    item.getRaw(),
                    item.getMappingStatus(),
                    item.getCandidateCode(),
                    candidateName,
                    item.getScore(),
                    item.getValueSummary(),
                    item.getVerdict(),
                    item.getReviewedBy(),
                    item.getReviewedAt(),
                    item.isAppliedToDictionary());
        }
    }

    @Service
    public static class ReviewService {

        private final ReviewItemRepository items;

        public ReviewService(ReviewItemRepository items) {
            this.items = items;
        }

        @Transactional(readOnly = true)
        public Page<ReviewItem> list(Long fileId, String status, PageRequest pageable) {
            boolean pendingOnly = !"all".equalsIgnoreCase(status);
            if (fileId == null) {
                return pendingOnly ? items.findByVerdictIsNull(pageable) : items.findAll(pageable);
            }
            return pendingOnly
                    ? items.findByFileIdAndVerdictIsNull(fileId, pageable)
                    : items.findByFileId(fileId, pageable);
        }

        /**
         * 판정을 저장한다.
         *
         * <p><b>사전 CSV는 건드리지 않는다.</b> 사전 반영은 담당자가 CLI로 하는 별도 단계다.
         */
        @Transactional
        public ReviewItem decide(Long id, String verdict, String note, String reviewer) {
            ReviewItem item = items.findById(id).orElseThrow(
                    () -> new ApiException(ErrorCode.REVIEW_NOT_FOUND, Map.of("id", id)));

            String trimmed = verdict == null ? "" : verdict.trim();
            if (trimmed.isEmpty()) {
                throw new ApiException(ErrorCode.VERDICT_REQUIRED);
            }
            // '승인'인데 후보가 없으면 무엇을 채택할지 알 수 없다.
            if (ReviewItem.VERDICT_ACCEPT.equals(trimmed) && item.getCandidateCode() == null) {
                throw new ApiException(ErrorCode.VERDICT_CANDIDATE_MISSING, Map.of("raw", item.getRaw()));
            }
            item.decide(trimmed, note, reviewer);
            return item;
        }
    }
}
