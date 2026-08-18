package com.awon.backend.standard;

import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** B6 기준치. 조건 확인 화면의 '기준치 세트 선택'과 결과 화면의 기준선에 쓰인다. */
@RestController
@RequestMapping("/api/v1")
public class StandardController {

    private final JdbcTemplate jdbc;

    public StandardController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /**
     * 기준 세트 목록.
     *
     * <p>화면의 드롭다운을 채우는 용도다. {@code source}가 함께 오므로
     * 법령에서 확인되지 않은 세트는 화면에서 구분해 표시할 수 있다.
     */
    @GetMapping("/standards")
    public Map<String, Object> sets() {
        List<Map<String, Object>> sets = jdbc.queryForList("""
                SELECT standard_set,
                       COUNT(*)                  AS item_count,
                       COUNT(DISTINCT item_code) AS distinct_items,
                       MIN(legal_basis)          AS legal_basis,
                       MIN(source)               AS source
                  FROM standard_limits
                 GROUP BY standard_set
                 ORDER BY standard_set
                """);

        List<String> regions = jdbc.queryForList("""
                SELECT DISTINCT region_grade FROM standard_limits
                 WHERE region_grade IS NOT NULL ORDER BY region_grade
                """, String.class);

        Integer unverified = jdbc.queryForObject(
                "SELECT COUNT(*) FROM standard_limits WHERE source <> 'law'", Integer.class);

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("sets", sets);
        body.put("region_grades", regions);
        body.put("scales", List.of(
                Map.of("value", "large", "label", "2,000㎥/일 이상"),
                Map.of("value", "small", "label", "2,000㎥/일 미만")));
        // 화면에 경고를 띄울 수 있도록 미확인 건수를 함께 준다.
        body.put("unverified_count", unverified == null ? 0 : unverified);
        return body;
    }

    /**
     * 특정 세트의 기준치 목록.
     *
     * <p>결과 화면이 그래프에 기준선을 그릴 때 쓴다.
     */
    @GetMapping("/standards/limits")
    public List<Map<String, Object>> limits(
            @RequestParam(name = "standard_set", defaultValue = "배출허용기준") String standardSet,
            @RequestParam(name = "region_grade", required = false) String regionGrade,
            @RequestParam(name = "item_code", required = false) String itemCode,
            @RequestParam(name = "scale") String scale) {

        scale = validateRequiredScale(scale);

        StringBuilder sql = new StringBuilder("""
                SELECT item_code, region_grade, scale, limit_min, limit_max, unit,
                       legal_basis, legal_article, source
                  FROM standard_limits
                 WHERE standard_set = ?
                """);
        List<Object> params = new ArrayList<>();
        params.add(standardSet);

        if (regionGrade != null && !regionGrade.isBlank()) {
            sql.append(" AND region_grade = ?");
            params.add(regionGrade);
        }
        if (itemCode != null && !itemCode.isBlank()) {
            sql.append(" AND item_code = ?");
            params.add(itemCode);
        }
        sql.append(" AND (scale IS NULL OR scale = ?)");
        params.add(scale);
        sql.append(" ORDER BY item_code, region_grade");

        return jdbc.queryForList(sql.toString(), params.toArray());
    }

    /**
     * 적재된 측정값을 기준치와 대조해 초과를 찾는다.
     *
     * <p>성적서에 딸려 온 기준치(reported_limit)가 아니라 법령 기준치로 판정한다.
     * 둘이 어긋나면 파일 쪽이 틀렸을 수 있으므로 함께 돌려준다.
     *
     * <p><b>원폐수는 제외한다.</b> 처리 전 물이라 기준을 넘는 것이 정상이고,
     * 섞어 세면 위반 건수가 통째로 부풀려진다.
     */
    @GetMapping("/standards/exceedances")
    public Map<String, Object> exceedances(
            @RequestParam(name = "standard_set", defaultValue = "배출허용기준") String standardSet,
            @RequestParam(name = "region_grade", defaultValue = "가지역") String regionGrade,
            @RequestParam(name = "scale", required = false) String scale,
            @RequestParam(name = "file_id", required = false) Long fileId) {

        scale = validateScale(scale);

        StringBuilder sql = new StringBuilder("""
                SELECT m.site_name, m.outlet, m.sample_type, m.measured_on,
                       m.item_code, m.value_num, m.unit,
                       s.limit_min, s.limit_max, s.source AS limit_source,
                       m.reported_limit,
                       CASE
                         WHEN s.limit_max IS NOT NULL AND m.value_num > s.limit_max THEN '상한 초과'
                         WHEN s.limit_min IS NOT NULL AND m.value_num < s.limit_min THEN '하한 미달'
                       END AS verdict
                  FROM measurements m
                  JOIN standard_limits s
                    ON s.item_code = m.item_code
                   AND s.standard_set = ?
                   AND (s.region_grade IS NULL OR s.region_grade = ?)
                   AND (s.scale IS NULL OR s.scale = ?)
                 WHERE m.value_num IS NOT NULL
                   AND (m.sample_type IS NULL OR m.sample_type <> '원폐수')
                   AND ((s.limit_max IS NOT NULL AND m.value_num > s.limit_max)
                     OR (s.limit_min IS NOT NULL AND m.value_num < s.limit_min))
                """);
        List<Object> params = new ArrayList<>();
        params.add(standardSet);
        params.add(regionGrade);
        params.add(scale == null ? "" : scale);

        if (fileId != null) {
            sql.append(" AND m.file_id = ?");
            params.add(fileId);
        }
        sql.append(" ORDER BY m.measured_on DESC, m.site_name LIMIT 100");

        List<Map<String, Object>> rows = jdbc.queryForList(sql.toString(), params.toArray());

        // 파일이 들고 온 기준치와 법령 기준치가 다른 경우. 어느 쪽이 맞는지는 사람이 본다.
        long mismatched = rows.stream()
                .filter(r -> r.get("reported_limit") != null && r.get("limit_max") != null)
                .filter(r -> !r.get("reported_limit").toString().equals(r.get("limit_max").toString()))
                .count();

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("standard_set", standardSet);
        body.put("region_grade", regionGrade);
        body.put("scale", scale);
        body.put("exceeded_count", rows.size());
        body.put("limit_mismatch_count", mismatched);
        body.put("items", rows);
        return body;
    }

    private String validateScale(String scale) {
        if (scale == null || scale.isBlank()) {
            return null;
        }
        if (!scale.equals("large") && !scale.equals("small")) {
            throw new ApiException(ErrorCode.STANDARD_SCALE_INVALID, Map.of("scale", scale));
        }
        return scale;
    }

    private String validateRequiredScale(String scale) {
        if (scale == null || scale.isBlank()) {
            throw new ApiException(ErrorCode.STANDARD_SCALE_REQUIRED, Map.of("scale", "required"));
        }
        return validateScale(scale);
    }
}
