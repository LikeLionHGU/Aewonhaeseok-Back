package com.awon.backend.standard;

import org.junit.jupiter.api.Test;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class StandardLimitCsvTest {

    @Test
    void verifiedLegalRowsAreUniqueAndScaleDependentItemsHaveBothScales() throws Exception {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                getClass().getResourceAsStream("/standards/standard_limits.csv"),
                StandardCharsets.UTF_8))) {
            List<String[]> rows = reader.lines().skip(1)
                    .filter(line -> !line.isBlank())
                    .map(line -> line.split(",", -1))
                    .toList();

            assertEquals(36, rows.size());
            assertTrue(rows.stream().allMatch(row -> "law".equals(row[11])));
            assertTrue(rows.stream().noneMatch(row -> "WQ-003".equals(row[1])));

            Set<String> keys = new HashSet<>();
            rows.forEach(row -> assertTrue(keys.add(row[0] + "|" + row[1] + "|" + row[3] + "|" + row[4])));

            for (String item : List.of("WQ-001", "WQ-002", "WQ-004")) {
                assertEquals(4, rows.stream().filter(row -> item.equals(row[1]) && "large".equals(row[4])).count());
                assertEquals(4, rows.stream().filter(row -> item.equals(row[1]) && "small".equals(row[4])).count());
            }
        }
    }
}
