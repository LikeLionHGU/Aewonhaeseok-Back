package com.awon.backend.file;

import com.awon.backend.common.PageResponse;
import com.awon.backend.mapping.MapperClient;
import com.awon.backend.file.dto.FileResponse;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;

/** B2 파일 접수. */
@RestController
@RequestMapping("/api/v1/files")
public class FileController {

    private final FileService service;
    private final MapperClient mapper;

    public FileController(FileService service, MapperClient mapper) {
        this.service = service;
        this.mapper = mapper;
    }

    /**
     * 업로드.
     *
     * <p>원본은 수정하지 않고 그대로 보관한다. 인코딩 판별과 헤더 탐지는
     * 매핑 실행 시점에 매핑 서비스가 수행한다.
     */
    @Operation(summary = "수질·폐수 원본 파일 업로드")
    @ApiResponse(responseCode = "201", description = "업로드 완료")
    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<FileResponse> upload(@RequestPart("file") MultipartFile file) {
        UploadedFile saved = service.upload(file);
        return ResponseEntity.status(HttpStatus.CREATED).body(FileResponse.of(saved));
    }

    @GetMapping
    public PageResponse<FileResponse> list(
            @RequestParam(required = false) FileStatus status,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {

        // 화면은 1-based, Spring Data는 0-based다.
        PageRequest pageable = PageRequest.of(
                Math.max(0, page - 1), size, Sort.by(Sort.Direction.DESC, "uploadedAt"));

        Page<UploadedFile> found = service.list(status, pageable);
        return PageResponse.from(found, service::describe);
    }

    @GetMapping("/{id}")
    public FileResponse get(@PathVariable Long id) {
        return service.describe(service.get(id));
    }

    /**
     * 원본 상위 10행 미리보기.
     *
     * <p>용어 검증 화면에서 값을 눈으로 확인하는 용도다. 파일 단위로 원본을 보고
     * 싶을 때 쓴다 — 컬럼 하나의 값 요약은 검증 대기열이 이미 함께 준다.
     */
    @GetMapping("/{id}/preview")
    public java.util.Map<String, Object> preview(@PathVariable Long id) {
        UploadedFile file = service.get(id);
        return mapper.preview(java.nio.file.Paths.get(file.getStoredPath()),
                file.getOriginalFilename());
    }
}
