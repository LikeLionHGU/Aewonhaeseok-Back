package com.awon.backend.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.media.Schema;
import org.springdoc.core.customizers.OpenApiCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

@Configuration
public class OpenApiConfig {

    @Bean
    OpenAPI awonOpenApi() {
        return new OpenAPI()
                .info(new Info()
                        .title("어원 수질·폐수 데이터 API")
                        .version("v1")
                        .description("기관별 수질·폐수 측정 파일을 표준 용어로 매핑하고, "
                                + "측정값 적재·기준치 비교·통계 분석을 제공하는 API입니다.")
                        .contact(new Contact().name("Awon Backend")));
    }

    /** 실제 Jackson 응답과 코드 생성용 OpenAPI 스키마의 필드명을 모두 snake_case로 맞춘다. */
    @Bean
    OpenApiCustomizer snakeCaseSchemaProperties() {
        return openApi -> {
            if (openApi.getComponents() == null || openApi.getComponents().getSchemas() == null) {
                return;
            }
            Set<Schema<?>> visited = Collections.newSetFromMap(new IdentityHashMap<>());
            openApi.getComponents().getSchemas().values()
                    .forEach(schema -> snakeCase(schema, visited));
        };
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    private void snakeCase(Schema schema, Set<Schema<?>> visited) {
        if (schema == null || !visited.add(schema)) {
            return;
        }
        Map<String, Schema> properties = schema.getProperties();
        if (properties != null && !properties.isEmpty()) {
            Map<String, Schema> renamed = new LinkedHashMap<>();
            properties.forEach((name, property) -> {
                renamed.put(toSnakeCase(name), property);
                snakeCase(property, visited);
            });
            schema.setProperties(renamed);
        }
        if (schema.getRequired() != null) {
            ArrayList<String> required = new ArrayList<>();
            for (Object name : schema.getRequired()) {
                required.add(toSnakeCase(String.valueOf(name)));
            }
            schema.setRequired(required);
        }
        snakeCase(schema.getItems(), visited);
        if (schema.getAdditionalProperties() instanceof Schema additional) {
            snakeCase(additional, visited);
        }
    }

    private String toSnakeCase(String value) {
        return value.replaceAll("([a-z0-9])([A-Z])", "$1_$2")
                .toLowerCase(Locale.ROOT);
    }
}
