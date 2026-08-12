package com.awon.backend.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;

@Configuration
public class MapperClientConfig {

    /**
     * Python 매핑 서비스 전용 클라이언트.
     *
     * <p>타임아웃을 넉넉히 잡은 이유: 매핑 자체는 9MB/104만행이 0.33초로 끝나지만,
     * 서비스가 막 뜬 직후에는 사전 적재와 라이브러리 로딩에 1초 남짓 걸린다.
     *
     * <p>이 클라이언트는 스프링이 설정한 JSON 변환기를 쓰지 않는다. 그래서
     * {@code spring.jackson.property-naming-strategy}가 적용되지 않는다.
     * 응답 DTO({@code MapperResponse})가 필드 이름을 직접 명시하는 이유다 —
     * 설정에 기대지 않으면 나중에 설정이 바뀌어도 깨지지 않는다.
     */
    @Bean
    public RestClient mapperRestClient(AwonProperties props) {
        Duration timeout = Duration.ofSeconds(props.mapper().timeoutSeconds());

        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(timeout);
        factory.setReadTimeout(timeout);

        return RestClient.builder()
                .baseUrl(props.mapper().baseUrl())
                .requestFactory(factory)
                .build();
    }
}
