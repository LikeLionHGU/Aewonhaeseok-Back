package com.awon.backend.mapping;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class MappingColumnTest {

    @Test
    void approvedReviewBecomesExactFileOverride() {
        MappingColumn column = new MappingColumn(
                3, "비오디", "비오디", MappingStatus.needs_review,
                "body", null, "WQ-001", "방류구A", null,
                "BOD", new BigDecimal("82.4"), "측정항목");

        column.applyReview("WQ-001", "생물화학적산소요구량", "측정항목");

        assertEquals(MappingStatus.exact, column.getStatus());
        assertEquals("review", column.getVia());
        assertEquals("WQ-001", column.getCode());
        assertEquals("WQ-001@방류구A", column.getOutputColumn());
        assertEquals("생물화학적산소요구량", column.getMatchedVariant());
        assertNull(column.getCandidateCode());
        assertNull(column.getScore());
    }
}
