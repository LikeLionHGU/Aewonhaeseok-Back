-- 물어볼래 백엔드 초기 스키마
--
-- 문자셋 주의: 반드시 utf8mb4. MySQL의 3바이트 utf8은 측정 단위 표기(㎎/L, ℃)와
-- 이온 표기(Cl⁻)에서 깨진다. 실제 수질 데이터 컬럼명에 이런 문자가 들어온다.
--
-- 이 스키마는 '우리 애플리케이션'의 테이블이다.
-- 표준 사전은 여기 없다 — 매핑 엔진이 CSV에서 직접 읽는다.
-- 사전을 DB로 옮기는 것은 검증 화면 완성 이후의 별도 작업이다.

-- ────────────────────────────────────────────────────────────────
-- 업로드된 원본 파일
-- 원본은 절대 수정하지 않는다(감사 대응). 경로와 해시만 여기 기록한다.
-- ────────────────────────────────────────────────────────────────
CREATE TABLE files (
    id                  BIGINT       NOT NULL AUTO_INCREMENT,
    original_filename   VARCHAR(500) NOT NULL,
    stored_path         VARCHAR(1000) NOT NULL,
    content_hash        CHAR(64)     NOT NULL COMMENT 'SHA-256. 같은 파일 재업로드 판별',
    size_bytes          BIGINT       NOT NULL,
    content_type        VARCHAR(100)     NULL,
    encoding_detected   VARCHAR(30)      NULL COMMENT 'utf-8-sig | cp949 | euc-kr',
    header_row          INT              NULL COMMENT '헤더가 몇 번째 행이었는지(0-based)',
    status              VARCHAR(20)  NOT NULL DEFAULT 'uploaded'
                        COMMENT 'uploaded|mapping|mapped|reviewing|completed|failed',
    uploaded_at         DATETIME(6)  NOT NULL,
    PRIMARY KEY (id),
    KEY idx_files_status (status),
    KEY idx_files_uploaded_at (uploaded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ────────────────────────────────────────────────────────────────
-- 매핑 실행 1회
-- 같은 파일을 사전이 자란 뒤 다시 돌리면 행이 하나 더 생긴다.
-- round_no로 전후 비교(발표 핵심 지표)를 만든다.
-- ────────────────────────────────────────────────────────────────
CREATE TABLE mapping_runs (
    id                  BIGINT       NOT NULL AUTO_INCREMENT,
    file_id             BIGINT       NOT NULL,
    round_no            INT          NOT NULL DEFAULT 1,
    dictionary_version  VARCHAR(40)  NOT NULL COMMENT 'dict-YYYY-MM-DD',
    dictionary_hash     VARCHAR(40)  NOT NULL COMMENT '같은 날 두 번 고쳐도 달라진다',
    header_row          INT          NOT NULL,
    total_columns       INT          NOT NULL,
    auto_mapped         INT          NOT NULL,
    needs_review        INT          NOT NULL,
    unmapped            INT          NOT NULL,
    auto_mapped_rate    DECIMAL(5,1) NOT NULL,
    ran_at              DATETIME(6)  NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_mapping_runs_file_round (file_id, round_no),
    CONSTRAINT fk_mapping_runs_file FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ────────────────────────────────────────────────────────────────
-- 컬럼별 판정 결과
-- 엔진의 MappingResult를 그대로 보존한다. 판정 근거를 나중에 설명할 수 있어야 한다.
--
-- raw에 개행이 들어올 수 있다. 엑셀에서 줄바꿈된 헤더가 그대로 온다
-- (예: '채수시각\n(WMCTM)'). VARCHAR로 문제없지만 화면에서 처리가 필요하다.
-- ────────────────────────────────────────────────────────────────
CREATE TABLE mapping_columns (
    id                  BIGINT       NOT NULL AUTO_INCREMENT,
    mapping_run_id      BIGINT       NOT NULL,
    column_index        INT          NOT NULL COMMENT '원본 파일에서의 열 순서',
    raw                 VARCHAR(500) NOT NULL COMMENT '원본 컬럼명. 절대 가공하지 않는다',
    normalized          VARCHAR(500)     NULL,
    status              VARCHAR(20)  NOT NULL COMMENT 'exact|fuzzy_auto|needs_review|unmapped',
    via                 VARCHAR(20)      NULL COMMENT 'body|paren|composite — 판정 경로',
    code                VARCHAR(10)      NULL COMMENT 'WQ-005 | MD-001. 자동 확정일 때만',
    candidate_code      VARCHAR(10)      NULL COMMENT 'needs_review일 때의 후보',
    site                VARCHAR(200)     NULL COMMENT '복합 컬럼명에서 떼어낸 지점 라벨',
    output_column       VARCHAR(300)     NULL COMMENT 'WQ-009@공촌천',
    matched_variant     VARCHAR(300)     NULL COMMENT '사전에서 매칭된 표기 원문',
    score               DECIMAL(4,1)     NULL COMMENT 'exact는 NULL. 점수로 맞춘 게 아니다',
    dict_type           VARCHAR(20)      NULL COMMENT '측정항목|메타',
    PRIMARY KEY (id),
    UNIQUE KEY uk_mapping_columns_run_index (mapping_run_id, column_index),
    KEY idx_mapping_columns_status (mapping_run_id, status),
    CONSTRAINT fk_mapping_columns_run FOREIGN KEY (mapping_run_id) REFERENCES mapping_runs (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ────────────────────────────────────────────────────────────────
-- 검증 대기열 + 사람 판정
--
-- ★ 이 테이블이 이 서비스의 핵심이다.
--   사용자 판정은 여기에만 쌓는다. 사전 CSV를 직접 고치면 다음 git merge에
--   전부 사라진다. 엔진의 apply_review()를 서버에서 호출하지 말 것.
--
-- exported_at은 tools/export_judgments.py가 뽑아간 시점이다.
-- 사전 담당자에게 넘어간 판정을 다시 넘기지 않기 위한 표시다.
-- ────────────────────────────────────────────────────────────────
CREATE TABLE review_items (
    id                     BIGINT       NOT NULL AUTO_INCREMENT,
    mapping_column_id      BIGINT       NOT NULL,
    file_id                BIGINT       NOT NULL COMMENT '조회 편의를 위한 비정규화',
    raw                    VARCHAR(500) NOT NULL,
    mapping_status         VARCHAR(20)  NOT NULL COMMENT 'needs_review|unmapped',
    candidate_code         VARCHAR(10)      NULL,
    score                  DECIMAL(4,1)     NULL,
    value_summary          JSON             NULL
                           COMMENT '실제 값 요약. 컬럼명만으로는 판단 불가하므로 필수',
    verdict                VARCHAR(20)      NULL COMMENT '승인|기각|표준코드(MD-012)',
    verdict_note           VARCHAR(1000)    NULL,
    reviewed_by            VARCHAR(100)     NULL COMMENT '서버가 기록. 프론트가 보내지 않는다',
    reviewed_at            DATETIME(6)      NULL,
    exported_at            DATETIME(6)      NULL COMMENT '사전 담당자에게 넘어간 시각',
    applied_to_dictionary  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at             DATETIME(6)  NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_review_items_column (mapping_column_id),
    KEY idx_review_items_pending (file_id, verdict),
    KEY idx_review_items_export (exported_at, reviewed_at),
    CONSTRAINT fk_review_items_column FOREIGN KEY (mapping_column_id) REFERENCES mapping_columns (id) ON DELETE CASCADE,
    CONSTRAINT fk_review_items_file FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
