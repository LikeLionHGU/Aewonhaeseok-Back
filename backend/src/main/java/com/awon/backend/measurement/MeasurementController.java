package com.awon.backend.measurement;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/** B5 측정값 적재·조회. */
@RestController
@RequestMapping("/api/v1")
public class MeasurementController {

    private final MeasurementIngestService ingest;
    private final JdbcTemplate jdbc;

    public MeasurementController(MeasurementIngestService ingest, JdbcTemplate jdbc) {
        this.ingest = ingest;
        this.jdbc = jdbc;
    }

    /**
     * 매핑된 파일의 측정값을 DB에 적재한다.
     *
     * <p>매핑이 먼저 끝나 있어야 한다. 다시 실행하면 기존 값이 갱신된다.
     */
    @PostMapping("/files/{fileId}/ingest")
    public MeasurementIngestService.Result ingest(@PathVariable Long fileId) {
        return ingest.ingest(fileId);
    }

    /**
     * 적재된 측정값 요약.
     *
     * <p>B7 자연어 분석이 붙기 전까지, 데이터가 실제로 들어왔는지 확인하는 용도다.
     */
    @GetMapping("/measurements/summary")
    public Map<String, Object> summary(@RequestParam(name = "file_id", required = false) Long fileId) {
        String where = fileId == null ? "" : " WHERE file_id = " + fileId;

        Map<String, Object> totals = jdbc.queryForMap("""
                SELECT COUNT(*)                AS total_values,
                       COUNT(DISTINCT item_code) AS distinct_items,
                       COUNT(DISTINCT site_name) AS distinct_sites,
                       MIN(measured_on)        AS first_date,
                       MAX(measured_on)        AS last_date
                  FROM measurements
                """ + where);

        List<Map<String, Object>> byItem = jdbc.queryForList("""
                SELECT item_code,
                       COUNT(*)        AS n,
                       ROUND(AVG(value_num), 3) AS avg_value,
                       ROUND(MIN(value_num), 3) AS min_value,
                       ROUND(MAX(value_num), 3) AS max_value
                  FROM measurements
                """ + where + """
                 GROUP BY item_code
                 ORDER BY n DESC
                """);

        // 기준 초과. 원폐수는 처리 전이라 기준을 넘는 것이 정상이므로 제외한다.
        // 이 구분이 없으면 초과 건수가 통째로 부풀려진다.
        List<Map<String, Object>> exceeded = jdbc.queryForList("""
                SELECT site_name, outlet, item_code, measured_on, value_num, reported_limit
                  FROM measurements
                 WHERE reported_limit IS NOT NULL
                   AND value_num > reported_limit
                   AND (sample_type IS NULL OR sample_type <> '원폐수')
                """ + (fileId == null ? "" : " AND file_id = " + fileId) + """
                 ORDER BY measured_on DESC
                 LIMIT 20
                """);

        return Map.of(
                "totals", totals,
                "by_item", byItem,
                "exceeded", exceeded);
    }
}
