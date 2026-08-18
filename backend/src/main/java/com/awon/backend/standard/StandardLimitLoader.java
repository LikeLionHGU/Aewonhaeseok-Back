package com.awon.backend.standard;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 기준치 표를 CSV에서 읽어 적재한다.
 *
 * <p>Flyway 마이그레이션에 값을 박아 넣지 않은 이유: 기준치는 법 개정으로
 * 실제로 바뀌는 값이라 CSV를 버전 관리하고 다시 띄우면 동기화되게 한다.
 * CSV를 고치고 다시 띄우면 반영되는 편이 운영에 맞는다.
 *
 * <p>CSV를 먼저 전부 파싱한 뒤 한 트랜잭션에서 기존 세트를 교체한다. 파싱이나
 * 적재가 실패하면 기존 기준치가 그대로 남는다.
 */
@Configuration
public class StandardLimitLoader {

    private static final Logger log = LoggerFactory.getLogger(StandardLimitLoader.class);

    private static final String CSV_PATH = "standards/standard_limits.csv";

    private static final String UPSERT = """
            INSERT INTO standard_limits (
                standard_set, item_code, region_grade, scale,
                limit_min, limit_max, unit,
                legal_basis, legal_article, effective_from, source, note, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON DUPLICATE KEY UPDATE
                limit_min = VALUES(limit_min),
                limit_max = VALUES(limit_max),
                unit = VALUES(unit),
                legal_basis = VALUES(legal_basis),
                legal_article = VALUES(legal_article),
                effective_from = VALUES(effective_from),
                source = VALUES(source),
                note = VALUES(note)
            """;

    @Bean
    public ApplicationRunner loadStandardLimits(JdbcTemplate jdbc,
                                                 PlatformTransactionManager transactionManager) {
        return args -> {
            ClassPathResource resource = new ClassPathResource(CSV_PATH);
            if (!resource.exists()) {
                log.warn("기준치 CSV가 없다: {}", CSV_PATH);
                return;
            }

            List<Object[]> rows = new ArrayList<>();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(resource.getInputStream(), StandardCharsets.UTF_8))) {

                String header = reader.readLine();   // 헤더 한 줄 버림
                if (header == null) {
                    return;
                }
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.isBlank()) {
                        continue;
                    }
                    rows.add(toParams(line.split(",", -1)));
                }
            } catch (IOException e) {
                log.error("기준치 CSV를 읽지 못했다", e);
                return;
            }

            if (rows.isEmpty()) {
                return;
            }
            TransactionTemplate transaction = new TransactionTemplate(transactionManager);
            transaction.executeWithoutResult(status -> {
                jdbc.update("DELETE FROM standard_limits WHERE standard_set = ?", "배출허용기준");
                jdbc.batchUpdate(UPSERT, rows);
            });

            Integer demo = jdbc.queryForObject(
                    "SELECT COUNT(*) FROM standard_limits WHERE source = 'demo'", Integer.class);
            log.info("기준치 {}건 적재", rows.size());
            if (demo != null && demo > 0) {
                log.warn("그중 {}건이 source=demo다. 법령 원문과 대조하기 전에는 "
                        + "판정 근거로 쓰지 말 것.", demo);
            }
        };
    }

    /** CSV 열 순서: standard_set, item_code, item_name, region_grade, scale, min, max, unit, ... */
    private Object[] toParams(String[] c) {
        return new Object[]{
                text(c, 0),
                text(c, 1),
                // 2번은 사람이 읽기 위한 항목명이라 저장하지 않는다. 정본은 표준코드다.
                text(c, 3),
                text(c, 4),
                decimal(c, 5),
                decimal(c, 6),
                text(c, 7),
                text(c, 8),
                text(c, 9),
                date(c, 10),
                textOr(c, 11, "demo"),
                text(c, 12),
                Timestamp.valueOf(OffsetDateTime.now().toLocalDateTime()),
        };
    }

    private String text(String[] c, int i) {
        if (i >= c.length) {
            return null;
        }
        String value = c[i].trim();
        return value.isEmpty() ? null : value;
    }

    private String textOr(String[] c, int i, String fallback) {
        String value = text(c, i);
        return value == null ? fallback : value;
    }

    private BigDecimal decimal(String[] c, int i) {
        String value = text(c, i);
        return value == null ? null : new BigDecimal(value);
    }

    private LocalDate date(String[] c, int i) {
        String value = text(c, i);
        return value == null ? null : LocalDate.parse(value);
    }
}
