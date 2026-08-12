-- B7 분석 실행 이력
--
-- 기능명세서가 요구한 것: "실행 ID·규칙 버전·사전 버전 함께 기록".
--
-- 왜 남기는가:
-- 이 서비스의 약속은 '근거 있는 통계'다. 같은 질문을 석 달 뒤에 다시 던졌을 때
-- 숫자가 달라졌다면, 데이터가 늘어난 것인지 사전이 바뀐 것인지 규칙이 바뀐 것인지
-- 구분할 수 있어야 한다. 그러려면 실행 시점의 조건을 통째로 남겨야 한다.
--
-- 생성된 SQL도 저장한다. 근거 상세 화면이 "이 숫자는 이 쿼리로 나왔습니다"를
-- 보여주는 데 쓴다.

CREATE TABLE analysis_runs (
    id                  BIGINT       NOT NULL AUTO_INCREMENT,

    -- 화면에 표시하고 공유 링크에 쓰는 식별자. 숫자 id를 그대로 노출하지 않는다.
    execution_id        CHAR(36)     NOT NULL,

    -- 무엇을 물었나. 조건 객체를 그대로 보관한다.
    -- 나중에 '같은 조건 재실행'과 '템플릿 저장'이 이 값을 쓴다.
    conditions          JSON         NOT NULL,

    -- 어떻게 답했나.
    generated_sql       TEXT         NOT NULL COMMENT '근거 상세 화면에 그대로 보여준다',

    -- 무엇을 기준으로 답했나. 셋 중 하나만 바뀌어도 결과가 달라질 수 있다.
    dictionary_version  VARCHAR(40)      NULL COMMENT '매핑에 쓰인 사전',
    ruleset_version     VARCHAR(40)  NOT NULL COMMENT '집계 규칙 버전',
    standard_set        VARCHAR(60)      NULL COMMENT '기준선에 쓴 기준 세트',
    region_grade        VARCHAR(20)      NULL,

    -- 결과 요약
    row_count           INT          NOT NULL,
    exceeded_count      INT          NOT NULL DEFAULT 0,
    elapsed_ms          INT          NOT NULL,
    truncated           BOOLEAN      NOT NULL DEFAULT FALSE
                        COMMENT '행 수 제한에 걸려 잘렸는가. 잘린 걸 숨기면 안 된다',

    ran_at              DATETIME(6)  NOT NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uk_analysis_execution (execution_id),
    KEY idx_analysis_ran_at (ran_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
