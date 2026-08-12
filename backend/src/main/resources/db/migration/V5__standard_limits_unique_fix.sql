-- 기준치 중복 적재 수정
--
-- 무슨 일이 있었나:
-- standard_limits의 UNIQUE (standard_set, item_code, region_grade, scale) 이
-- 중복을 막지 못했다. scale이 NULL이기 때문이다.
--
-- ★ MySQL은 UNIQUE 인덱스에서 NULL을 서로 다른 값으로 취급한다.
--   (NULL != NULL 이므로 표준 SQL 동작이기도 하다)
--   그래서 ON DUPLICATE KEY UPDATE가 한 번도 걸리지 않았고,
--   서버를 재시작할 때마다 기준치가 한 벌씩 더 쌓였다. 21행 → 42행.
--
--   결과적으로 그래프의 기준선이 두 번씩 그려졌다. 값이 같아 눈에 잘 띄지 않는데,
--   조건이 늘어나면 조용히 틀린 집계로 이어질 수 있는 종류의 버그다.
--
-- 해결: NULL을 빈 문자열로 바꾼 생성 컬럼을 만들고 그걸로 유일성을 건다.
--       데이터에는 NULL을 그대로 두어 "해당 없음"의 의미를 잃지 않는다.

-- 1) 중복 정리 — 같은 조합에서 가장 최근 행만 남긴다.
DELETE s FROM standard_limits s
  JOIN (
      SELECT standard_set, item_code,
             COALESCE(region_grade, '') AS rg,
             COALESCE(scale, '')        AS sc,
             MAX(id) AS keep_id
        FROM standard_limits
       GROUP BY standard_set, item_code, rg, sc
      HAVING COUNT(*) > 1
  ) dup
    ON  dup.standard_set = s.standard_set
   AND  dup.item_code    = s.item_code
   AND  dup.rg           = COALESCE(s.region_grade, '')
   AND  dup.sc           = COALESCE(s.scale, '')
 WHERE s.id <> dup.keep_id;

-- 2) NULL을 견디는 유일 키로 교체
ALTER TABLE standard_limits
    DROP INDEX uk_standard_limits;

ALTER TABLE standard_limits
    ADD COLUMN region_grade_key VARCHAR(20)
        GENERATED ALWAYS AS (COALESCE(region_grade, '')) STORED,
    ADD COLUMN scale_key VARCHAR(20)
        GENERATED ALWAYS AS (COALESCE(scale, '')) STORED;

ALTER TABLE standard_limits
    ADD UNIQUE KEY uk_standard_limits
        (standard_set, item_code, region_grade_key, scale_key);
