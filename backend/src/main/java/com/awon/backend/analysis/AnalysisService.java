package com.awon.backend.analysis;

import com.awon.backend.auth.CurrentUser;
import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
import com.awon.backend.common.PageResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.sql.Timestamp;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * B7 — 조건을 받아 통계를 낸다.
 *
 * <h2>가드레일</h2>
 * 기능명세서가 요구한 네 가지를 모두 구조로 강제한다.
 * <ul>
 *   <li><b>SELECT만</b> — 사용자가 SQL을 보내지 않는다. 서버가 조립하므로 DML이 될 수 없다.</li>
 *   <li><b>타임아웃</b> — 쿼리 단위로 건다.</li>
 *   <li><b>행 수 제한</b> — 제한에 걸리면 잘렸다고 응답에 표시한다. 숨기면 안 된다.</li>
 *   <li><b>읽기 전용 계정</b> — 운영에서는 SELECT 권한만 가진 계정을 쓴다(배포 시 설정).</li>
 * </ul>
 *
 * <p>값은 전부 바인딩 파라미터로 들어간다. SQL 문자열에 섞이는 것은 열거형
 * ({@code Bucket}, {@code Metric})뿐이라 임의 표현식이 들어올 수 없다.
 */
@Service
public class AnalysisService {

    private static final Logger log = LoggerFactory.getLogger(AnalysisService.class);

    /** 집계 규칙 버전. 산식을 바꾸면 올린다. 과거 실행과 결과가 달라지는 이유를 추적하기 위함이다. */
    static final String RULESET_VERSION = "rules-2026-08-11";

    private static final int MAX_ROWS = 5_000;
    private static final int QUERY_TIMEOUT_SECONDS = 10;

    private final JdbcTemplate jdbc;
    private final tools.jackson.databind.ObjectMapper json;
    private final CurrentUser currentUser;

    public AnalysisService(JdbcTemplate jdbc, tools.jackson.databind.ObjectMapper json,
                           CurrentUser currentUser) {
        this.jdbc = jdbc;
        this.json = json;
        this.currentUser = currentUser;
    }

    public record Result(String executionId,
                         List<String> assumptions,
                         List<Map<String, Object>> series,
                         List<Map<String, Object>> limits,
                         int exceededCount,
                         Map<String, Object> meta) {
    }

    @Transactional
    public Result run(AnalysisRequest raw) {
        AnalysisRequest request = raw.withDefaults();
        long ownerId = currentUser.id();

        List<Object> params = new ArrayList<>();
        String sql = buildSql(request, params, ownerId);

        long started = System.nanoTime();
        List<Map<String, Object>> series = query(sql, params);
        int elapsedMs = (int) ((System.nanoTime() - started) / 1_000_000);

        boolean truncated = series.size() >= MAX_ROWS;

        List<Map<String, Object>> limits = loadLimits(request);
        int exceeded = countExceeded(series, limits);

        String executionId = UUID.randomUUID().toString();
        String dictionaryVersion = latestDictionaryVersion(ownerId);

        record(executionId, request, request.assumptions(), series, limits, sql,
                dictionaryVersion, series.size(), exceeded, elapsedMs, truncated, ownerId);

        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("execution_id", executionId);
        meta.put("dictionary_version", dictionaryVersion);
        meta.put("ruleset_version", RULESET_VERSION);
        meta.put("row_count", series.size());
        meta.put("elapsed_ms", elapsedMs);
        meta.put("truncated", truncated);
        // 근거 상세 화면이 그대로 보여준다. 숨길 이유가 없다.
        meta.put("generated_sql", sql);

        return new Result(executionId, request.assumptions(), series, limits, exceeded, meta);
    }

    public Map<String, Object> detail(String executionId) {
        List<Map<String, Object>> found = jdbc.queryForList("""
                SELECT execution_id, conditions, assumptions, series, limits, generated_sql,
                       dictionary_version, ruleset_version, standard_set, region_grade, scale,
                       row_count, exceeded_count, elapsed_ms, truncated, ran_at
                 FROM analysis_runs
                 WHERE execution_id = ? AND owner_user_id = ?
                """, executionId, currentUser.id());
        if (found.isEmpty()) {
            throw new ApiException(ErrorCode.ANALYSIS_NOT_FOUND, Map.of("execution_id", executionId));
        }
        Map<String, Object> result = new LinkedHashMap<>(found.get(0));
        parseJsonField(result, "conditions", Map.class, Map.of());
        parseJsonField(result, "assumptions", List.class, List.of());
        parseJsonField(result, "series", List.class, List.of());
        parseJsonField(result, "limits", List.class, List.of());
        return result;
    }

    public PageResponse<Map<String, Object>> history(int page, int size) {
        int safePage = Math.max(1, page);
        int safeSize = Math.min(200, Math.max(1, size));
        int offset = (safePage - 1) * safeSize;
        List<Map<String, Object>> rawItems = jdbc.queryForList("""
                SELECT execution_id, conditions, dictionary_version, ruleset_version,
                       standard_set, region_grade, scale, row_count, exceeded_count,
                       elapsed_ms, truncated, ran_at
                  FROM analysis_runs
                 WHERE owner_user_id = ?
                 ORDER BY ran_at DESC
                 LIMIT ? OFFSET ?
                """, currentUser.id(), safeSize, offset);
        List<Map<String, Object>> items = rawItems.stream().map(raw -> {
            Map<String, Object> item = new LinkedHashMap<>(raw);
            parseJsonField(item, "conditions", Map.class, Map.of());
            return item;
        }).toList();

        Long total = jdbc.queryForObject(
                "SELECT COUNT(*) FROM analysis_runs WHERE owner_user_id = ?",
                Long.class, currentUser.id());
        return new PageResponse<>(items, safePage, safeSize, total == null ? 0 : total);
    }

    /** 분석 당시 조건에 해당하는 실제 적재 행. 근거 화면이 출처까지 추적할 때 쓴다. */
    public PageResponse<Map<String, Object>> measurementRows(String executionId, int page, int size) {
        Map<String, Object> detail = detail(executionId);
        AnalysisRequest request;
        try {
            request = json.convertValue(detail.get("conditions"), AnalysisRequest.class).withDefaults();
        } catch (RuntimeException e) {
            throw new ApiException(ErrorCode.ANALYSIS_NOT_FOUND,
                    Map.of("execution_id", executionId, "cause", "conditions_unreadable"));
        }

        int safePage = Math.max(1, page);
        int safeSize = Math.min(200, Math.max(1, size));
        List<Object> params = new ArrayList<>();
        String where = measurementWhere(request, params, currentUser.id());

        List<Object> rowParams = new ArrayList<>(params);
        rowParams.add(safeSize);
        rowParams.add((safePage - 1) * safeSize);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT m.id AS measurement_id, m.file_id, f.original_filename AS filename,
                       m.source_row, m.source_column, m.source_column_index,
                       m.site_name, m.outlet, m.sample_type,
                       m.measured_on, m.measured_at, m.period_label, m.item_code, m.unit,
                       m.value_num, m.value_text, m.is_numeric, m.reported_limit, m.quality_flag
                  FROM measurements m
                  JOIN files f ON f.id = m.file_id
                """ + where + """
                 ORDER BY m.measured_on, m.file_id, m.source_row, m.source_column_index
                 LIMIT ? OFFSET ?
                """, rowParams.toArray());

        Long total = jdbc.queryForObject("SELECT COUNT(*) FROM measurements m" + where,
                Long.class, params.toArray());
        return new PageResponse<>(rows, safePage, safeSize, total == null ? 0 : total);
    }

    /**
     * 조건에서 SQL을 조립한다.
     *
     * <p>결측 처리 방침: 값이 없는 행은 애초에 적재되지 않았고, 숫자로 바꿀 수 없던 값은
     * {@code value_num IS NULL}로 남아 있다. 집계에서 이들을 제외하되 몇 건이
     * 제외됐는지 함께 센다 — 조용히 빼면 평균이 왜곡된 줄 모른다.
     */
    private String buildSql(AnalysisRequest r, List<Object> params, long ownerId) {
        StringBuilder sql = new StringBuilder();
        sql.append("SELECT ").append(r.bucket().expression()).append(" AS bucket,\n")
           .append("       m.item_code,\n")
           .append("       ROUND(").append(r.metric().expression()).append(", 4) AS value,\n")
           .append("       COUNT(*) AS n,\n")
           .append("       SUM(CASE WHEN m.value_num IS NULL THEN 1 ELSE 0 END) AS missing,\n")
           .append("       MIN(m.unit) AS unit\n")
           .append("  FROM measurements m\n")
           .append(" WHERE EXISTS (SELECT 1 FROM files f_owner WHERE f_owner.id = m.file_id AND f_owner.owner_user_id = ?)\n");
        params.add(ownerId);

        appendIn(sql, params, "m.site_name", r.siteNames());
        appendIn(sql, params, "m.outlet", r.outlets());
        appendIn(sql, params, "m.item_code", r.itemCodes());

        if (r.sampleType() != null && !r.sampleType().isBlank()) {
            sql.append("   AND m.sample_type = ?\n");
            params.add(r.sampleType());
        }
        if (r.from() != null) {
            sql.append("   AND m.measured_on >= ?\n");
            params.add(java.sql.Date.valueOf(r.from()));
        }
        if (r.to() != null) {
            sql.append("   AND m.measured_on <= ?\n");
            params.add(java.sql.Date.valueOf(r.to()));
        }

        sql.append("   AND m.measured_on IS NOT NULL\n")
           .append(" GROUP BY bucket, m.item_code\n")
           .append(" ORDER BY bucket, m.item_code\n")
           .append(" LIMIT ").append(MAX_ROWS).append("\n");
        return sql.toString();
    }

    /** IN 절도 값 개수만큼 물음표를 만들어 바인딩한다. 문자열로 이어 붙이지 않는다. */
    private void appendIn(StringBuilder sql, List<Object> params, String column, List<String> values) {
        if (values == null || values.isEmpty()) {
            return;
        }
        String placeholders = values.stream().map(v -> "?").collect(Collectors.joining(", "));
        sql.append("   AND ").append(column).append(" IN (").append(placeholders).append(")\n");
        params.addAll(values);
    }

    private String measurementWhere(AnalysisRequest r, List<Object> params, long ownerId) {
        StringBuilder where = new StringBuilder(" WHERE EXISTS (SELECT 1 FROM files f_owner WHERE f_owner.id = m.file_id AND f_owner.owner_user_id = ?)\n");
        params.add(ownerId);
        appendIn(where, params, "m.site_name", r.siteNames());
        appendIn(where, params, "m.outlet", r.outlets());
        appendIn(where, params, "m.item_code", r.itemCodes());
        if (r.sampleType() != null && !r.sampleType().isBlank()) {
            where.append(" AND m.sample_type = ?\n");
            params.add(r.sampleType());
        }
        if (r.from() != null) {
            where.append(" AND m.measured_on >= ?\n");
            params.add(java.sql.Date.valueOf(r.from()));
        }
        if (r.to() != null) {
            where.append(" AND m.measured_on <= ?\n");
            params.add(java.sql.Date.valueOf(r.to()));
        }
        where.append(" AND m.measured_on IS NOT NULL\n");
        return where.toString();
    }

    private List<Map<String, Object>> query(String sql, List<Object> params) {
        return jdbc.query(connection -> {
            var ps = connection.prepareStatement(sql);
            ps.setQueryTimeout(QUERY_TIMEOUT_SECONDS);
            for (int i = 0; i < params.size(); i++) {
                ps.setObject(i + 1, params.get(i));
            }
            return ps;
        }, (rs, rowNum) -> {
            Map<String, Object> row = new LinkedHashMap<>();
            var meta = rs.getMetaData();
            for (int i = 1; i <= meta.getColumnCount(); i++) {
                row.put(meta.getColumnLabel(i), rs.getObject(i));
            }
            return row;
        });
    }

    /** 그래프에 그릴 기준선. 지역구분을 안 고르면 기준선이 없다 — 임의로 고르지 않는다. */
    private List<Map<String, Object>> loadLimits(AnalysisRequest r) {
        if (r.regionGrade() == null || r.regionGrade().isBlank()) {
            return List.of();
        }
        StringBuilder sql = new StringBuilder("""
                SELECT item_code, scale, limit_min, limit_max, unit, source, legal_basis
                  FROM standard_limits
                 WHERE standard_set = ?
                   AND (region_grade IS NULL OR region_grade = ?)
                   AND (scale IS NULL OR scale = ?)
                """);
        String scale = r.scale() == null ? "" : r.scale().name();
        List<Object> params = new ArrayList<>(List.of(r.standardSet(), r.regionGrade(), scale));
        appendIn(sql, params, "item_code", r.itemCodes());
        return jdbc.queryForList(sql.toString(), params.toArray());
    }

    /** 집계값이 기준을 넘은 구간 수. 원자료 단위 초과는 /standards/exceedances가 따로 센다. */
    private int countExceeded(List<Map<String, Object>> series, List<Map<String, Object>> limits) {
        if (limits.isEmpty()) {
            return 0;
        }
        Map<String, Map<String, Object>> byItem = new LinkedHashMap<>();
        limits.forEach(l -> byItem.put(String.valueOf(l.get("item_code")), l));

        int count = 0;
        for (Map<String, Object> point : series) {
            Map<String, Object> limit = byItem.get(String.valueOf(point.get("item_code")));
            if (limit == null || point.get("value") == null) {
                continue;
            }
            double value = ((Number) point.get("value")).doubleValue();
            Number max = (Number) limit.get("limit_max");
            Number min = (Number) limit.get("limit_min");
            if ((max != null && value > max.doubleValue())
                    || (min != null && value < min.doubleValue())) {
                count++;
            }
        }
        return count;
    }

    /** 적재에 쓰인 사전 버전. 여러 파일이 섞여 있으면 가장 최근 것을 쓴다. */
    private String latestDictionaryVersion(long ownerId) {
        List<String> versions = jdbc.queryForList(
                "SELECT ir.dictionary_version FROM ingestion_runs ir JOIN files f ON f.id = ir.file_id "
                        + "WHERE f.owner_user_id = ? ORDER BY ir.ran_at DESC LIMIT 1",
                String.class, ownerId);
        return versions.isEmpty() ? null : versions.get(0);
    }

    private void record(String executionId, AnalysisRequest r, List<String> assumptions,
                        List<Map<String, Object>> series, List<Map<String, Object>> limits,
                        String sql, String dictionaryVersion,
                        int rowCount, int exceeded, int elapsedMs, boolean truncated,
                        long ownerId) {
        String conditions;
        String assumptionsJson;
        String seriesJson;
        String limitsJson;
        try {
            conditions = json.writeValueAsString(r);
            assumptionsJson = json.writeValueAsString(assumptions);
            seriesJson = json.writeValueAsString(series);
            limitsJson = json.writeValueAsString(limits);
        } catch (RuntimeException e) {
            throw new IllegalStateException("분석 결과 직렬화 실패", e);
        }
        jdbc.update("""
                INSERT INTO analysis_runs (
                    owner_user_id, execution_id, conditions, assumptions, series, limits, generated_sql,
                    dictionary_version, ruleset_version, standard_set, region_grade,
                    scale, row_count, exceeded_count, elapsed_ms, truncated, ran_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                ownerId, executionId, conditions, assumptionsJson, seriesJson, limitsJson, sql,
                dictionaryVersion, RULESET_VERSION, r.standardSet(), r.regionGrade(),
                r.scale() == null ? null : r.scale().name(),
                rowCount, exceeded, elapsedMs, truncated,
                Timestamp.valueOf(OffsetDateTime.now().toLocalDateTime()));
    }

    private void parseJsonField(Map<String, Object> target, String field, Class<?> type,
                                Object fallback) {
        Object raw = target.get(field);
        if (raw == null) {
            target.put(field, fallback);
            return;
        }
        try {
            target.put(field, json.readValue(String.valueOf(raw), type));
        } catch (RuntimeException e) {
            log.warn("저장된 분석 JSON을 읽지 못함: {}", field, e);
            target.put(field, fallback);
        }
    }
}
