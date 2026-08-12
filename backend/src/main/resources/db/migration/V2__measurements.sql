-- B5 측정값 적재 — 세로형 테이블
--
-- 원본 파일은 가로형(컬럼마다 항목)이다. 그대로는 질문에 답할 수 없다.
-- "작년 대비 BOD 추이"를 구하려면 항목이 값이어야지 컬럼이면 안 되기 때문이다.
-- 그래서 한 행에 하나의 측정값이 오도록 편다.
--
--   원본 : 강정천 | 2024-03-14 | 온도 16.7 | BOD 0.6 | COD 0.2
--   적재 : (강정천, 2024-03-14, WQ-009, 16.7)
--          (강정천, 2024-03-14, WQ-001, 0.6)
--          (강정천, 2024-03-14, WQ-003, 0.2)
--
-- 아래 설계는 2026-08-11에 폐수 데모 데이터를 실제로 매핑해보고 나온 결과를 반영한 것이다.

-- ────────────────────────────────────────────────────────────────
-- 측정값
-- ────────────────────────────────────────────────────────────────
CREATE TABLE measurements (
    id                BIGINT       NOT NULL AUTO_INCREMENT,

    -- 출처 추적. "이 숫자가 어느 파일 어느 컬럼에서 왔나"에 답할 수 있어야 한다.
    -- 근거 상세 화면이 원본 행을 보여주려면 필요하고, 잘못 적재된 값을 되돌릴 때도 쓴다.
    file_id           BIGINT       NOT NULL,
    mapping_run_id    BIGINT       NOT NULL,
    source_column     VARCHAR(500) NOT NULL COMMENT '원본 컬럼명. 가공하지 않는다',
    source_row        INT          NOT NULL COMMENT '원본 파일에서 몇 번째 행이었나',

    -- ── 어디서 쟀나 ──────────────────────────────────────────────
    -- 하천 데이터는 site_name만 채워지고 outlet은 비어 있다.
    -- 폐수 데이터는 사업장(MD-034) + 방류구(MD-033)가 함께 온다.
    -- 한 사업장에 방류구가 여럿이고 배출허용기준이 방류구마다 따로 정해진다.
    site_name         VARCHAR(200)     NULL COMMENT '하천명·측정소명·사업장명',
    outlet            VARCHAR(100)     NULL COMMENT '방류구. 폐수에만 있다',

    -- ★ 원폐수인지 방류수인지.
    --   같은 BOD 값이라도 처리 전이면 정상이고 처리 후면 심각한 문제다.
    --   구분 없이 한 테이블에 섞이면 평균·추이가 통째로 무의미해진다.
    --
    --   표준 사전에 이 축의 용어가 아직 없다(2026-08-11 확인. '시료구분'·'원폐수'·
    --   '방류수' 모두 unmapped). 그래서 표준코드가 아니라 원문 문자열로 받아 둔다.
    --   사전에 등재되면 코드 컬럼으로 옮긴다.
    sample_type       VARCHAR(50)      NULL COMMENT '원폐수 | 방류수. 사전 미등재라 원문 보관',

    -- ── 언제 쟀나 ────────────────────────────────────────────────
    -- 파일마다 날짜 표기가 제각각이다. 제주는 '시료채취일' 한 칸, 충남은
    -- '측정년월'과 '회차'가 따로다. 적재할 때 하나의 축으로 합친다.
    measured_on       DATE             NULL,
    measured_at       DATETIME(6)      NULL COMMENT 'TMS처럼 시각까지 있는 경우',
    period_label      VARCHAR(50)      NULL COMMENT '1분기, 2024년 등 원본 표기 보존',

    -- ── 무엇을 쟀나 ──────────────────────────────────────────────
    item_code         VARCHAR(10)  NOT NULL COMMENT 'WQ-005 등 표준 측정항목 코드',
    unit              VARCHAR(20)      NULL COMMENT '사전의 표준 단위로 통일한 뒤의 값',

    -- ── 얼마였나 ─────────────────────────────────────────────────
    -- 숫자로 못 바꾸는 값이 실제로 온다: '불검출', '<0.001', '-', 빈칸.
    -- 원문을 버리면 나중에 왜 비었는지 설명할 수 없으므로 둘 다 남긴다.
    value_num         DECIMAL(18,6)    NULL,
    value_text        VARCHAR(100)     NULL COMMENT '원본 표기. 숫자 변환 실패 시 근거',
    is_numeric        BOOLEAN      NOT NULL DEFAULT TRUE,

    -- ★ 성적서에 함께 실려 온 배출허용기준.
    --   측정값 옆 칸에 기준치가 같이 찍혀 나오는 서식이 실제로 있다.
    --   이건 '측정한 값'이 아니므로 measurements의 값으로 적재하면 안 되고,
    --   같은 행의 참고 정보로 붙인다.
    --   법령에서 뽑은 정식 기준치 테이블(B6)과는 별개다 — 파일이 틀렸을 수도 있으니
    --   대조해서 어긋나면 경고를 띄우는 용도로 쓴다.
    reported_limit    DECIMAL(18,6)    NULL COMMENT '파일에 함께 온 기준치. 정본 아님',

    -- ── 품질 ─────────────────────────────────────────────────────
    -- 값 범위, 미래 일자, 결측 검출 결과.
    -- TMS 고시 별표 1(비정상자료 선별기준)을 아직 확보하지 못해 임시 규칙을 쓴다.
    -- 별표를 받으면 법이 정한 기준으로 교체한다.
    quality_flag      VARCHAR(30)      NULL COMMENT 'ok | out_of_range | future_date | non_numeric',

    created_at        DATETIME(6)  NOT NULL,

    PRIMARY KEY (id),

    -- 같은 파일을 두 번 적재해도 값이 중복되지 않게 한다.
    UNIQUE KEY uk_measurements_source (mapping_run_id, source_row, source_column),

    -- 자연어 분석이 실제로 던질 질문 모양에 맞춘 인덱스.
    -- "특정 항목의 기간별 추이", "특정 지점의 전체 항목"이 주된 패턴이다.
    KEY idx_measurements_item_date (item_code, measured_on),
    KEY idx_measurements_site (site_name, item_code, measured_on),
    KEY idx_measurements_outlet (outlet, item_code, measured_on),
    KEY idx_measurements_file (file_id),

    CONSTRAINT fk_measurements_file FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE,
    CONSTRAINT fk_measurements_run FOREIGN KEY (mapping_run_id) REFERENCES mapping_runs (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ────────────────────────────────────────────────────────────────
-- 적재 이력
--
-- 한 번의 적재가 몇 행을 넣었고 몇 행을 버렸는지 남긴다.
-- "왜 이 파일은 값이 적지?"에 답할 수 있어야 한다.
-- ────────────────────────────────────────────────────────────────
CREATE TABLE ingestion_runs (
    id                BIGINT       NOT NULL AUTO_INCREMENT,
    file_id           BIGINT       NOT NULL,
    mapping_run_id    BIGINT       NOT NULL,

    source_rows       INT          NOT NULL COMMENT '원본 행 수',
    measured_columns  INT          NOT NULL COMMENT '측정항목으로 확정된 컬럼 수',
    inserted_values   INT          NOT NULL COMMENT '적재된 측정값 수',
    skipped_values    INT          NOT NULL COMMENT '빈칸 등으로 건너뛴 수',
    flagged_values    INT          NOT NULL COMMENT '품질 경고가 붙은 수',

    -- 어떤 사전으로 매핑된 결과를 적재했는지. 사전이 바뀌면 결과도 달라진다.
    dictionary_version VARCHAR(40) NOT NULL,

    ran_at            DATETIME(6)  NOT NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uk_ingestion_run (mapping_run_id),
    CONSTRAINT fk_ingestion_file FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE,
    CONSTRAINT fk_ingestion_run FOREIGN KEY (mapping_run_id) REFERENCES mapping_runs (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
