package com.awon.backend.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** application.yml의 awon.* 설정. */
@ConfigurationProperties(prefix = "awon")
public record AwonProperties(Storage storage, Mapper mapper) {

    /** 업로드 원본 보관. 원본은 절대 수정하지 않는다(감사 대응). */
    public record Storage(String root) {
    }

    /** Python 매핑 서비스. 외부에 노출하지 않고 스프링만 호출한다. */
    public record Mapper(String baseUrl, int timeoutSeconds) {
    }
}
