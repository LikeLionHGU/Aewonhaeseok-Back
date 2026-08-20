package com.awon.backend.analysis;

import com.awon.backend.auth.CurrentUser;
import com.awon.backend.common.PageResponse;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/** B7 분석. 조건 확인 화면과 결과 화면이 쓴다. */
@RestController
@RequestMapping("/api/v1")
public class AnalysisController {

    private final AnalysisService service;
    private final JdbcTemplate jdbc;
    private final CurrentUser currentUser;

    public AnalysisController(AnalysisService service, JdbcTemplate jdbc, CurrentUser currentUser) {
        this.service = service;
        this.jdbc = jdbc;
        this.currentUser = currentUser;
    }

    /**
     * 분석 실행.
     *
     * <p>사용자는 조건만 보낸다. SQL은 서버가 조립한다.
     * 응답의 {@code assumptions}는 "지정하지 않아 서버가 채운 것"이라, 화면이
     * "이렇게 해석했습니다"를 보여주는 데 쓴다.
     */
    @PostMapping("/analyses")
    public AnalysisService.Result run(@RequestBody AnalysisRequest request) {
        return service.run(request);
    }

    /**
     * 선택 가능한 조건 목록.
     *
     * <p>조건 확인 화면의 드롭다운을 채운다. 실제 적재된 데이터에서 뽑으므로
     * 고를 수 없는 값이 화면에 뜨지 않는다.
     */
    @GetMapping("/analyses/options")
    public Map<String, Object> options() {
        long ownerId = currentUser.id();
        return Map.of(
                "sites", jdbc.queryForList("""
                        SELECT DISTINCT m.site_name FROM measurements m JOIN files f ON f.id=m.file_id
                         WHERE f.owner_user_id=? AND m.site_name IS NOT NULL ORDER BY m.site_name
                        """, String.class, ownerId),
                "outlets", jdbc.queryForList("""
                        SELECT DISTINCT m.outlet FROM measurements m JOIN files f ON f.id=m.file_id
                         WHERE f.owner_user_id=? AND m.outlet IS NOT NULL ORDER BY m.outlet
                        """, String.class, ownerId),
                "items", jdbc.queryForList("""
                        SELECT m.item_code, COUNT(*) AS n
                          FROM measurements m JOIN files f ON f.id=m.file_id
                         WHERE f.owner_user_id=? GROUP BY m.item_code ORDER BY m.item_code
                        """, ownerId),
                "sample_types", jdbc.queryForList("""
                        SELECT DISTINCT m.sample_type FROM measurements m JOIN files f ON f.id=m.file_id
                         WHERE f.owner_user_id=? AND m.sample_type IS NOT NULL ORDER BY m.sample_type
                        """, String.class, ownerId),
                "period", jdbc.queryForMap("""
                        SELECT MIN(m.measured_on) AS first_date, MAX(m.measured_on) AS last_date
                          FROM measurements m JOIN files f ON f.id=m.file_id
                         WHERE f.owner_user_id=? AND m.measured_on IS NOT NULL
                        """, ownerId),
                "buckets", List.of("month", "quarter", "year", "none"),
                "metrics", List.of("avg", "max", "min", "count"),
                "scales", List.of(
                        Map.of("value", "large", "label", "2,000㎥/일 이상"),
                        Map.of("value", "small", "label", "2,000㎥/일 미만")));
    }

    /** 실행 이력. 홈 화면의 '최근 분석 기록'에 쓴다. */
    @GetMapping("/analyses")
    public PageResponse<Map<String, Object>> history(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        return service.history(page, size);
    }

    /**
     * 근거 상세.
     *
     * <p>결과 화면의 "근거 상세 보기"가 갈 곳이다. 실행에 쓰인 조건과
     * 생성된 SQL을 그대로 보여준다. 숫자만 던지고 끝내지 않는다는 것이
     * 이 서비스의 약속이다.
     */
    @GetMapping("/analyses/{executionId}")
    public Map<String, Object> detail(@PathVariable String executionId) {
        return service.detail(executionId);
    }

    @GetMapping("/analyses/{executionId}/measurements")
    public PageResponse<Map<String, Object>> measurements(
            @PathVariable String executionId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "50") int size) {
        return service.measurementRows(executionId, page, size);
    }
}
