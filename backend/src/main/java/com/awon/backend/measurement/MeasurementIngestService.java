package com.awon.backend.measurement;

import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
import com.awon.backend.file.UploadedFile;
import com.awon.backend.file.UploadedFileRepository;
import com.awon.backend.mapping.MapperClient;
import com.awon.backend.mapping.MappingRun;
import com.awon.backend.mapping.MappingRunRepository;
// Boot 4는 Jackson 3을 쓴다. 패키지가 com.fasterxml이 아니라 tools.jackson이다.
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.math.BigDecimal;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.sql.Date;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.sql.Types;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.LinkedHashMap;

/**
 * B5 — 매핑된 파일의 측정값을 DB에 적재한다.
 *
 * <p>가로형(컬럼마다 항목)을 세로형(한 행에 하나의 값)으로 펴는 일은 Python이 한다.
 * 파일을 여는 것도 컬럼을 판정하는 것도 거기서 하는데 값만 가져와 다시 파싱하면
 * 인코딩·헤더 탐지 로직이 두 벌이 되기 때문이다. 여기서는 저장만 한다.
 */
@Service
public class MeasurementIngestService {

    private static final Logger log = LoggerFactory.getLogger(MeasurementIngestService.class);

    /** 한 번에 밀어 넣을 행 수. 너무 크면 메모리, 너무 작으면 왕복이 늘어난다. */
    private static final int BATCH_SIZE = 1_000;

    private static final String INSERT_SQL = """
            INSERT INTO measurements (
                file_id, mapping_run_id, source_column, source_column_index, source_row,
                site_name, outlet, sample_type,
                measured_on, measured_at, period_label,
                item_code, unit, value_num, value_text, is_numeric,
                reported_limit, quality_flag, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON DUPLICATE KEY UPDATE
                value_num = VALUES(value_num),
                value_text = VALUES(value_text),
                is_numeric = VALUES(is_numeric),
                reported_limit = VALUES(reported_limit),
                quality_flag = VALUES(quality_flag)
            """;

    private final UploadedFileRepository files;
    private final MappingRunRepository runs;
    private final MapperClient mapper;
    private final JdbcTemplate jdbc;
    private final ObjectMapper json = new ObjectMapper();

    public MeasurementIngestService(UploadedFileRepository files, MappingRunRepository runs,
                                    MapperClient mapper, JdbcTemplate jdbc) {
        this.files = files;
        this.runs = runs;
        this.mapper = mapper;
        this.jdbc = jdbc;
    }

    public record Result(long fileId, long mappingRunId, String dictionaryVersion,
                         int sourceRows, int measuredColumns,
                         int insertedValues, int skippedValues, int flaggedValues) {
    }

    /**
     * 파일 하나를 적재한다.
     *
     * <p>매핑이 먼저 끝나 있어야 한다. 같은 파일을 다시 적재하면 값이 갱신된다
     * (중복 삽입이 아니라) — 사전이 자란 뒤 다시 돌리는 경우가 정상 흐름이기 때문이다.
     */
    @Transactional
    public Result ingest(Long fileId) {
        UploadedFile file = files.findById(fileId)
                .orElseThrow(() -> new ApiException(ErrorCode.FILE_NOT_FOUND, Map.of("id", fileId)));
        MappingRun run = runs.findLatestWithColumns(fileId)
                .orElseThrow(() -> new ApiException(ErrorCode.MAPPING_NOT_FOUND,
                        Map.of("file_id", fileId)));

        Path stored = Paths.get(file.getStoredPath());
        Counters counters = new Counters();

        Map<Integer, Map<String, Object>> overrides = new LinkedHashMap<>();
        run.getColumns().stream()
                .filter(column -> column.getCode() != null)
                .forEach(column -> {
                    Map<String, Object> override = new LinkedHashMap<>();
                    override.put("code", column.getCode());
                    if (column.getDictType() != null) {
                        override.put("dict_type", column.getDictType());
                    }
                    overrides.put(column.getColumnIndex(), override);
                });

        // 파일 단위 교체 정책. 새 매핑 회차로 재적재해도 과거 값과 합쳐지지 않는다.
        jdbc.update("DELETE FROM measurements WHERE file_id = ?", file.getId());
        jdbc.update("DELETE FROM ingestion_runs WHERE file_id = ?", file.getId());

        String dictionaryVersion = mapper.streamRows(stored, file.getOriginalFilename(), overrides,
                reader -> consume(reader, file.getId(), run.getId(), counters));

        recordIngestionRun(file.getId(), run.getId(), dictionaryVersion, counters);

        log.info("적재 완료 file={} rows={} values={} skipped={} flagged={}",
                fileId, counters.sourceRows, counters.inserted, counters.skipped, counters.flagged);

        return new Result(file.getId(), run.getId(), dictionaryVersion,
                counters.sourceRows, counters.measuredColumns,
                counters.inserted, counters.skipped, counters.flagged);
    }

    /** NDJSON 한 줄씩 읽어 배치로 밀어 넣는다. 전부 모아두지 않는다. */
    private String consume(BufferedReader reader, Long fileId, Long runId, Counters counters) {
        List<Object[]> batch = new ArrayList<>(BATCH_SIZE);
        String dictionaryVersion = "unknown";

        try {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) {
                    continue;
                }
                JsonNode node = json.readTree(line);

                // 첫 줄은 요약이다.
                if ("meta".equals(node.path("kind").asText())) {
                    dictionaryVersion = node.path("dictionary_version").asText("unknown");
                    counters.sourceRows = node.path("source_rows").asInt();
                    counters.measuredColumns = node.path("measured_columns").asInt();
                    continue;
                }

                batch.add(toParams(node, fileId, runId));
                if (node.hasNonNull("quality_flag")) {
                    counters.flagged++;
                }
                if (!node.path("is_numeric").asBoolean(true)) {
                    counters.skipped++;
                }

                if (batch.size() >= BATCH_SIZE) {
                    counters.inserted += flush(batch);
                }
            }
            counters.inserted += flush(batch);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        return dictionaryVersion;
    }

    private int flush(List<Object[]> batch) {
        if (batch.isEmpty()) {
            return 0;
        }
        jdbc.batchUpdate(INSERT_SQL, batch);
        int size = batch.size();
        batch.clear();
        return size;
    }

    private Object[] toParams(JsonNode n, Long fileId, Long runId) {
        return new Object[]{
                fileId,
                runId,
                n.path("source_column").asText(""),
                n.path("source_column_index").asInt(),
                n.path("source_row").asInt(),
                text(n, "site_name"),
                text(n, "outlet"),
                text(n, "sample_type"),
                date(n, "measured_on"),
                null,                       // measured_at — TMS 시각 지원 시 채운다
                text(n, "period_label"),
                n.path("item_code").asText(),
                text(n, "unit"),
                decimal(n, "value_num"),
                text(n, "value_text"),
                n.path("is_numeric").asBoolean(true),
                decimal(n, "reported_limit"),
                text(n, "quality_flag"),
                Timestamp.valueOf(OffsetDateTime.now().toLocalDateTime()),
        };
    }

    private String text(JsonNode n, String field) {
        JsonNode value = n.get(field);
        return value == null || value.isNull() ? null : value.asText();
    }

    private BigDecimal decimal(JsonNode n, String field) {
        JsonNode value = n.get(field);
        return value == null || value.isNull() ? null : value.decimalValue();
    }

    private Date date(JsonNode n, String field) {
        String value = text(n, field);
        return value == null ? null : Date.valueOf(value);
    }

    private void recordIngestionRun(Long fileId, Long runId, String version, Counters c) {
        jdbc.update(connection -> {
            PreparedStatement ps = connection.prepareStatement("""
                    INSERT INTO ingestion_runs (
                        file_id, mapping_run_id, source_rows, measured_columns,
                        inserted_values, skipped_values, flagged_values,
                        dictionary_version, ran_at
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    ON DUPLICATE KEY UPDATE
                        source_rows = VALUES(source_rows),
                        measured_columns = VALUES(measured_columns),
                        inserted_values = VALUES(inserted_values),
                        skipped_values = VALUES(skipped_values),
                        flagged_values = VALUES(flagged_values),
                        dictionary_version = VALUES(dictionary_version),
                        ran_at = VALUES(ran_at)
                    """);
            ps.setLong(1, fileId);
            ps.setLong(2, runId);
            ps.setInt(3, c.sourceRows);
            ps.setInt(4, c.measuredColumns);
            ps.setInt(5, c.inserted);
            ps.setInt(6, c.skipped);
            ps.setInt(7, c.flagged);
            ps.setString(8, version);
            ps.setTimestamp(9, Timestamp.valueOf(OffsetDateTime.now().toLocalDateTime()));
            return ps;
        });
    }

    private static final class Counters {
        int sourceRows;
        int measuredColumns;
        int inserted;
        int skipped;
        int flagged;
    }
}
