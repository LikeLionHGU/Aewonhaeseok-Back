package com.awon.backend.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.media.ObjectSchema;
import io.swagger.v3.oas.models.media.Schema;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class OpenApiConfigTest {

    @Test
    void generatedSchemaPropertiesUseSnakeCase() {
        Schema<?> file = new ObjectSchema()
                .addProperty("sizeBytes", new Schema<>().type("integer"))
                .addProperty("measuredFrom", new Schema<>().type("string"));
        file.setRequired(List.of("sizeBytes"));
        OpenAPI api = new OpenAPI().components(new Components().addSchemas("FileResponse", file));

        new OpenApiConfig().snakeCaseSchemaProperties().customise(api);

        assertTrue(file.getProperties().containsKey("size_bytes"));
        assertTrue(file.getProperties().containsKey("measured_from"));
        assertFalse(file.getProperties().containsKey("sizeBytes"));
        assertTrue(file.getRequired().contains("size_bytes"));
    }
}
