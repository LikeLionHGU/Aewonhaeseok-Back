package com.awon.backend.dictionary;

import com.awon.backend.mapping.MapperClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * B8 사전 운영.
 *
 * <p>사전을 실제로 들고 있는 것은 Python 매핑 서비스다. 여기서는 중계만 한다.
 * 프론트는 Python 서비스를 직접 호출하지 않는다.
 */
@RestController
@RequestMapping("/api/v1")
public class DictionaryController {

    private final MapperClient mapper;
    private final TermNameCache terms;

    public DictionaryController(MapperClient mapper, TermNameCache terms) {
        this.mapper = mapper;
        this.terms = terms;
    }

    /** 결과 화면의 "사전 버전" 칸에 그대로 표시된다. */
    @GetMapping("/dictionary/version")
    public Map<String, Object> version() {
        return mapper.dictionaryVersion();
    }

    /**
     * 사전 리로드.
     *
     * <p>사전 CSV를 git merge로 갱신한 뒤 이걸 부르지 않으면 옛날 사전이 계속 쓰인다.
     * 매핑률이 갑자기 이상하면 이것부터 확인할 것.
     */
    @PostMapping("/admin/reload-dictionary")
    public Map<String, Object> reload() {
        Map<String, Object> result = mapper.reloadDictionary();
        // 사전이 바뀌었으면 표준명 캐시도 비운다.
        // 안 그러면 새로 생긴 코드의 이름이 영영 안 나온다.
        terms.invalidate();
        return result;
    }
}
