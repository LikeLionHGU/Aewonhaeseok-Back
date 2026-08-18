package com.awon.backend.mapping;

import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
import com.awon.backend.mapping.dto.MapperResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Map;
import java.util.function.Function;

/**
 * Python 매핑 서비스 호출.
 *
 * <p>파일 경로가 아니라 파일 내용을 보낸다. 두 서비스가 같은 디스크를 공유한다고
 * 가정하지 않기 위해서다. 컨테이너로 분리해도 볼륨을 맞출 필요가 없다.
 */
@Component
public class MapperClient {

    private static final Logger log = LoggerFactory.getLogger(MapperClient.class);

    private final RestClient client;
    private final tools.jackson.databind.ObjectMapper json;

    public MapperClient(RestClient mapperRestClient, tools.jackson.databind.ObjectMapper json) {
        this.client = mapperRestClient;
        this.json = json;
    }

    /** 파일 하나를 매핑한다. 실측상 9MB/104만 행이 0.33초라 동기로 처리한다. */
    public MapperResponse map(Path file, String originalFilename) {
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new NamedFileResource(file, originalFilename));

        try {
            return client.post()
                    .uri("/map")
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(form)
                    .retrieve()
                    .body(MapperResponse.class);
        } catch (RestClientException e) {
            throw translate(e, Map.of("filename", originalFilename));
        }
    }

    /**
     * 파일을 세로형 측정값 레코드로 펴서 받는다.
     *
     * <p>응답이 NDJSON 스트림이라 통째로 메모리에 올리지 않는다. 104만 행 파일은
     * 레코드가 수백만 개가 되는데, 배열 하나로 받으면 양쪽 다 감당하지 못한다.
     * 호출자가 한 줄씩 처리한다.
     *
     * @param consumer 줄 단위 처리기. 스트림이 닫히기 전에 소비를 끝내야 한다.
     */
    public <T> T streamRows(Path file, String originalFilename,
                            Map<Integer, Map<String, Object>> overrides,
                            Function<BufferedReader, T> consumer) {
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new NamedFileResource(file, originalFilename));
        form.add("overrides", json.writeValueAsString(overrides));

        try {
            return client.post()
                    .uri("/rows")
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(form)
                    .exchange((request, response) -> {
                        if (response.getStatusCode().isError()) {
                            throw new ApiException(ErrorCode.MAPPER_FAILED,
                                    Map.of("status", response.getStatusCode().value()));
                        }
                        try (BufferedReader reader = new BufferedReader(
                                new InputStreamReader(response.getBody(), StandardCharsets.UTF_8))) {
                            return consumer.apply(reader);
                        }
                    });
        } catch (ApiException e) {
            throw e;
        } catch (RestClientException | UncheckedIOException e) {
            throw translate(e, Map.of("filename", originalFilename));
        }
    }

    /** 원본 상위 몇 행. 검증 화면에서 값을 눈으로 확인하는 용도다. */
    public Map<String, Object> preview(Path file, String originalFilename) {
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new NamedFileResource(file, originalFilename));
        try {
            return client.post()
                    .uri("/preview")
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(form)
                    .retrieve()
                    .body(JSON_OBJECT);
        } catch (RestClientException e) {
            throw translate(e, Map.of("filename", originalFilename));
        }
    }

    /** 컬럼명 하나만 매핑. 화면 미리보기용. */
    public Map<String, Object> mapColumn(String name) {
        try {
            return client.post()
                    .uri("/map/column")
                    .body(Map.of("name", name))
                    .retrieve()
                    .body(JSON_OBJECT);
        } catch (RestClientException e) {
            throw translate(e, Map.of("name", name));
        }
    }

    /**
     * 표준코드 → 한글 표준명.
     *
     * <p>검증 화면이 후보 코드(MD-006)만 보여주면 사람이 판단할 수 없다.
     * 자주 바뀌지 않으므로 호출한 쪽에서 캐시해 쓴다.
     */
    public Map<String, Object> dictionaryTerms() {
        try {
            return client.get()
                    .uri("/dictionary/terms")
                    .retrieve()
                    .body(JSON_OBJECT);
        } catch (RestClientException e) {
            throw translate(e, Map.of());
        }
    }

    /** 사전 버전 조회. 엔진의 VERSION.json을 그대로 돌려준다. */
    public Map<String, Object> dictionaryVersion() {
        try {
            return client.get()
                    .uri("/dictionary/version")
                    .retrieve()
                    .body(JSON_OBJECT);
        } catch (RestClientException e) {
            throw translate(e, Map.of());
        }
    }

    /**
     * 사전 리로드.
     *
     * <p>사전은 매핑 서비스가 시작할 때 1회만 메모리에 올린다. git merge로 CSV가
     * 바뀌어도 이걸 부르기 전까지는 옛날 사전을 쓴다.
     */
    public Map<String, Object> reloadDictionary() {
        try {
            return client.post()
                    .uri("/admin/reload-dictionary")
                    .retrieve()
                    .body(JSON_OBJECT);
        } catch (RestClientException e) {
            throw translate(e, Map.of());
        }
    }

    /** 사전 응답은 엔진이 주는 형태를 그대로 통과시키므로 구조를 고정하지 않는다. */
    private static final ParameterizedTypeReference<Map<String, Object>> JSON_OBJECT =
            new ParameterizedTypeReference<>() {
            };

    private ApiException translate(RuntimeException e, Map<String, Object> detail) {
        log.error("매핑 서비스 호출 실패", e);
        // 연결 자체가 안 되면 서비스가 안 떠 있는 것이다. 사용자에게 다르게 안내한다.
        boolean unreachable = e.getCause() instanceof java.net.ConnectException
                || e.getCause() instanceof java.net.UnknownHostException;
        return new ApiException(
                unreachable ? ErrorCode.MAPPER_UNAVAILABLE : ErrorCode.MAPPER_FAILED, detail, e);
    }

    /**
     * multipart에 원본 파일명을 실어 보내기 위한 래퍼.
     *
     * <p>디스크에는 UUID로 저장돼 있어 그대로 보내면 확장자가 사라진다.
     * 매핑 엔진은 확장자로 csv/xlsx를 구분하므로 원본 이름이 필요하다.
     */
    private static final class NamedFileResource extends FileSystemResource {
        private final String filename;

        private NamedFileResource(Path path, String filename) {
            super(path);
            this.filename = filename;
        }

        @Override
        public String getFilename() {
            return filename;
        }
    }
}
