-- B6 기준치 — 법령이 정한 배출허용기준·환경기준
--
-- 왜 필요한가:
-- "BOD가 기준을 넘었나"에 답하려면 기준이 몇인지 알아야 하는데,
-- 표준 사전에는 그 숫자가 없다. legal_basis 칸에 조항 이름만 문자열로 들어 있다.
-- 그래서 법령 원문에서 숫자를 옮겨 별도 테이블로 만든다.
--
-- ★ 구조가 단순하지 않다.
--   별표 13의 배출허용기준은 항목 하나에 값 하나가 아니다.
--   지역구분(청정·가·나·특례) × 배출규모(2천㎥/일 이상·미만) 조합마다 값이 다르다.
--   같은 BOD라도 청정지역 대규모 사업장과 나지역 소규모 사업장의 기준이 다르다.
--   이걸 하나의 값으로 뭉개면 초과 판정이 틀린다.
--
-- ★ 수소이온농도는 상한만으로 판정할 수 없다.
--   pH는 5.8~8.6 같은 범위라 아래로 벗어나도 위반이다.
--   그래서 상한·하한을 따로 둔다.

CREATE TABLE standard_limits (
    id             BIGINT       NOT NULL AUTO_INCREMENT,

    -- 어떤 기준 세트인가. 배출허용기준과 하천 환경기준은 성격이 다르다.
    standard_set   VARCHAR(60)  NOT NULL
                   COMMENT '배출허용기준 | 하천생활환경기준 | 방류수수질기준 | 먹는물수질기준',

    item_code      VARCHAR(10)  NOT NULL COMMENT 'WQ-005 등 표준 측정항목 코드',

    -- 적용 조건. 해당 없으면 NULL이고, 그때는 항목당 단일 기준이라는 뜻이다.
    -- 특정수질유해물질은 지역·규모와 무관하게 단일 기준인 경우가 많다.
    region_grade   VARCHAR(20)      NULL COMMENT '청정지역 | 가지역 | 나지역 | 특례지역',
    scale          VARCHAR(20)      NULL COMMENT 'large(2천㎥/일 이상) | small(미만)',

    -- 범위형 기준을 담기 위해 상·하한을 따로 둔다.
    -- 대부분의 항목은 limit_max만 채워진다(이하). pH만 둘 다 쓴다.
    limit_min      DECIMAL(18,6)    NULL COMMENT '이 값 미만이면 위반. pH 등',
    limit_max      DECIMAL(18,6)    NULL COMMENT '이 값 초과면 위반',
    unit           VARCHAR(20)      NULL,

    -- 근거. 사전과 같은 방식으로 조문 단위까지 남긴다.
    -- "이 기준을 누가 정했나"에 답하지 못하면 판정 결과를 신뢰할 수 없다.
    legal_basis    VARCHAR(200)     NULL COMMENT '물환경보전법 시행규칙 별표 13 등',
    legal_article  VARCHAR(60)      NULL,
    effective_from DATE             NULL,

    -- ★ 이 값이 법령에서 온 것인지 데모용으로 채운 것인지 구분한다.
    --   섞이면 발표에서 실측 기준처럼 쓰게 된다.
    --   'demo'인 값은 화면에도 표시하지 않는 편이 안전하다.
    source         VARCHAR(20)  NOT NULL DEFAULT 'demo' COMMENT 'law | demo',

    note           VARCHAR(500)     NULL,
    created_at     DATETIME(6)  NOT NULL,

    PRIMARY KEY (id),

    -- 같은 조건에 기준이 둘일 수는 없다.
    UNIQUE KEY uk_standard_limits (standard_set, item_code, region_grade, scale),
    KEY idx_standard_limits_lookup (item_code, standard_set)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
