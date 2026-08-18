package com.awon.backend.dictionary;

import com.awon.backend.mapping.MapperClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

/**
 * 표준코드 → 한글 표준명 캐시.
 *
 * <p>검증 화면이 후보 코드만 보여주면 사람이 판단할 수 없다.
 * {@code MD-006}이 아니라 {@code MD-006 측정일자}로 보여야 한다.
 *
 * <p>매핑 서비스를 매번 부르지 않고 한 번 받아 들고 있는다. 사전이 바뀌면
 * 리로드할 때 함께 비운다 — 그러지 않으면 새 코드의 이름이 영영 안 나온다.
 */
@Component
public class TermNameCache {

    private static final Logger log = LoggerFactory.getLogger(TermNameCache.class);

    private final MapperClient mapper;
    private final AtomicReference<Map<String, Map<String, Object>>> cache =
            new AtomicReference<>(null);

    public TermNameCache(MapperClient mapper) {
        this.mapper = mapper;
    }

    /** 표준코드의 한글 이름. 모르면 null을 돌려주고 화면은 코드만 표시한다. */
    @SuppressWarnings("unchecked")
    public String nameOf(String code) {
        if (code == null || code.isBlank()) {
            return null;
        }
        Map<String, Map<String, Object>> terms = cache.get();
        if (terms == null) {
            terms = load();
        }
        Map<String, Object> term = terms.get(code);
        return term == null ? null : (String) term.get("name");
    }

    public boolean contains(String code) {
        return code != null && terms().containsKey(code);
    }

    public String typeOf(String code) {
        Map<String, Object> term = terms().get(code);
        return term == null ? null : String.valueOf(term.get("dict_type"));
    }

    public Map<String, Map<String, Object>> terms() {
        Map<String, Map<String, Object>> terms = cache.get();
        return terms == null ? load() : terms;
    }

    /** 사전이 바뀌었을 때 비운다. 리로드 엔드포인트가 부른다. */
    public void invalidate() {
        cache.set(null);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Map<String, Object>> load() {
        try {
            Map<String, Object> body = mapper.dictionaryTerms();
            Map<String, Map<String, Object>> terms =
                    (Map<String, Map<String, Object>>) body.get("terms");
            Map<String, Map<String, Object>> resolved = terms == null ? Map.of() : terms;
            cache.set(resolved);
            return resolved;
        } catch (RuntimeException e) {
            // 이름을 못 가져와도 검증 화면은 떠야 한다. 코드만 보여주면 된다.
            log.warn("표준명을 가져오지 못했다. 코드만 표시한다.", e);
            return Map.of();
        }
    }
}
