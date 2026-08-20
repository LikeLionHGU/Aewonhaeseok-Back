package com.awon.backend.openapi;

import io.swagger.v3.oas.annotations.media.Schema;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class OpenApiSelfControllerSchemaTest {
    @Test
    void requestsPerMinuteDocumentsSelfServiceLimit() throws NoSuchMethodException {
        Schema schema = OpenApiSelfController.IssueRequest.class
                .getDeclaredMethod("requestsPerMinute").getAnnotation(Schema.class);

        assertEquals("1", schema.minimum());
        assertEquals("60", schema.maximum());
        assertEquals("60", schema.defaultValue());
    }
}
