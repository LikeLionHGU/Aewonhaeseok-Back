package com.awon.backend.mapping;

import jakarta.validation.constraints.NotBlank;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 컬럼명 하나만 매핑해 본다.
 *
 * <p>온톨로지 인수인계 문서가 "백엔드가 쓸 함수 4개"로 꼽은 {@code map_column()}이다.
 * 검증 화면에서 '다른 항목 선택'을 누르거나, 사용자가 컬럼명을 직접 입력해
 * 어떤 코드로 잡히는지 확인할 때 쓴다.
 *
 * <p>파일을 올릴 필요가 없어 가볍다.
 */
@RestController
@RequestMapping("/api/v1/mapping")
public class ColumnPreviewController {

    private final MapperClient mapper;

    public ColumnPreviewController(MapperClient mapper) {
        this.mapper = mapper;
    }

    @PostMapping("/preview")
    public Map<String, Object> preview(@RequestBody Request request) {
        return mapper.mapColumn(request.name());
    }

    public record Request(@NotBlank(message = "컬럼명을 입력해 주세요.") String name) {
    }
}
