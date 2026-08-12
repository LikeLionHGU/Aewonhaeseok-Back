package com.awon.backend.common;

import org.springframework.data.domain.Page;

import java.util.List;
import java.util.function.Function;

/** 목록 응답 공통 형태. API 명세서 §1의 페이징 규약과 같다. */
public record PageResponse<T>(List<T> items, int page, int size, long total) {

    /** Spring Data의 0-based page를 화면이 쓰는 1-based로 바꿔 내보낸다. */
    public static <E, T> PageResponse<T> from(Page<E> source, Function<E, T> mapper) {
        return new PageResponse<>(
                source.getContent().stream().map(mapper).toList(),
                source.getNumber() + 1,
                source.getSize(),
                source.getTotalElements());
    }
}
