package com.awon.backend.analysis;

import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
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

    public AnalysisController(AnalysisService service, JdbcTemplate jdbc) {
        this.service = service;
        this.jdbc = jdbc;
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
        return Map.of(
                "sites", jdbc.queryForList("""
                        SELECT DISTINCT site_name FROM measurements
                         WHERE site_name IS NOT NULL ORDER BY site_name
                        """, String.class),
                "outlets", jdbc.queryForList("""
                        SELECT DISTINCT outlet FROM measurements
                         WHERE outlet IS NOT NULL ORDER BY outlet
                        """, String.class),
                "items", jdbc.queryForList("""
                        SELECT item_code, COUNT(*) AS n
                          FROM measurements GROUP BY item_code ORDER BY item_code
                        """),
                "sample_types", jdbc.queryForList("""
                        SELECT DISTINCT sample_type FROM measurements
                         WHERE sample_type IS NOT NULL ORDER BY sample_type
                        """, String.class),
                "period", jdbc.queryForMap("""
                        SELECT MIN(measured_on) AS first_date, MAX(measured_on) AS last_date
                          FROM measurements WHERE measured_on IS NOT NULL
                        """),
                "buckets", List.of("month", "quarter", "year", "none"),
                "metrics", List.of("avg", "max", "min", "count"));
    }

    /** 실행 이력. 홈 화면의 '최근 분석 기록'에 쓴다. */
    @GetMapping("/analyses")
    public PageResponse<Map<String, Object>> history(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {

        int offset = Math.max(0, page - 1) * size;
        List<Map<String, Object>> items = jdbc.queryForList("""
                SELECT execution_id, conditions, dictionary_version, ruleset_version,
                       standard_set, region_grade, row_count, exceeded_count,
                       elapsed_ms, truncated, ran_at
                  FROM analysis_runs
                 ORDER BY ran_at DESC
                 LIMIT ? OFFSET ?
                """, size, offset);

        Integer total = jdbc.queryForObject("SELECT COUNT(*) FROM analysis_runs", Integer.class);
        return new PageResponse<>(items, Math.max(1, page), size, total == null ? 0 : total);
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
        List<Map<String, Object>> found = jdbc.queryForList("""
                SELECT execution_id, conditions, generated_sql,
                       dictionary_version, ruleset_version, standard_set, region_grade,
                       row_count, exceeded_count, elapsed_ms, truncated, ran_at
                  FROM analysis_runs
                 WHERE execution_id = ?
                """, executionId);

        if (found.isEmpty()) {
            throw new ApiException(ErrorCode.ANALYSIS_NOT_FOUND, Map.of("execution_id", executionId));
        }
        return found.get(0);
    }
}
