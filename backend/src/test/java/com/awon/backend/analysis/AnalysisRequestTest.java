package com.awon.backend.analysis;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AnalysisRequestTest {

    @Test
    void missingRegionAndScaleNeverGuessLegalLimitConditions() {
        AnalysisRequest request = new AnalysisRequest(
                null, null, null, null, null, null, null, null, null, null, null);

        AnalysisRequest defaults = request.withDefaults();

        assertEquals(AnalysisRequest.Bucket.month, defaults.bucket());
        assertEquals(AnalysisRequest.Metric.avg, defaults.metric());
        assertEquals("배출허용기준", defaults.standardSet());
        assertEquals(null, defaults.regionGrade());
        assertEquals(null, defaults.scale());
        assertTrue(request.assumptions().stream().anyMatch(it -> it.contains("지역구분")));
        assertTrue(request.assumptions().stream().anyMatch(it -> it.contains("폐수배출규모")));
    }
}
