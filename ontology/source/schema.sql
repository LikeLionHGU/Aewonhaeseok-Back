-- ============================================================================
--  수질 데이터 표준 용어 사전 — PostgreSQL 스키마
--  ---------------------------------------------------------------------------
--  사전(dictionary) 2개:
--    measurement_terms  측정항목  (근거: 법령 — 물환경보전법 시행규칙 별표 13 등)
--    metadata_terms     관측 메타 (근거: 공공데이터 표준 / 소스 관행)
--
--  지원 테이블 3개:
--    term_sources       출처 레지스트리 — 동의어가 어느 시스템에서 왔는지
--    term_synonyms      동의어 1건 = 1행. 출처·수집일이 동의어마다 붙는다.
--    unresolved_columns 매칭 실패한 컬럼 큐 — 사전이 자라는 입구
--
--  왜 동의어가 별도 테이블인가:
--    "동의어마다 출처와 수집일"을 기록하려면 1:N이어야 한다.
--    파이프 구분 문자열(BOD5|비오디|...)에는 출처를 붙일 자리가 없다.
--    엑셀의 파이프 형태는 사람이 훑어보기 위한 표현일 뿐이고,
--    v_dictionary_flat 뷰가 그 형태를 언제든 다시 만들어 준다.
--
--  적용:  psql -d <db> -f schema.sql
-- ============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- 유사도 폴백 매칭용

-- ---------------------------------------------------------------------------
-- 0. 공통 함수
-- ---------------------------------------------------------------------------

-- 컬럼명 정규화 키. 대소문자·공백·구두점·밑줄·하이픈을 모두 제거한다.
--   '총 질소'      -> '총질소'
--   'T-N' / 'T_N'  -> 'tn'
--   'itemBod'      -> 'itembod'
--   '생물학적 산소요구량(BOD_L당mg)' -> '생물학적산소요구량bodl당mg'
-- 괄호 안 내용은 일부러 지우지 않는다. '노말헥산추출물질함유량(광유류)'와
-- '(동식물유지류)'가 같은 키로 뭉개지면 서로 다른 법정 항목이 충돌한다.
CREATE OR REPLACE FUNCTION wq_normalize(p_text text)
RETURNS text
LANGUAGE sql
IMMUTABLE STRICT PARALLEL SAFE
AS $$
  SELECT lower(regexp_replace(p_text, '[^[:alnum:]가-힣]', '', 'g'))
$$;

COMMENT ON FUNCTION wq_normalize(text) IS
  '컬럼명 매칭용 정규화 키 생성. IMMUTABLE이므로 생성열·인덱스에 사용 가능.';

CREATE OR REPLACE FUNCTION wq_set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- 1. measurement_terms — 측정항목 사전 (법령 근거)
-- ---------------------------------------------------------------------------
CREATE TABLE measurement_terms (
  code                text PRIMARY KEY
                        CHECK (code ~ '^WQ-[0-9]{3}$'),

  -- 표준명은 "법령 원문 표기 그대로"가 원칙이다.
  -- 예: '플로오르(불소)함유량' (X '플루오린'), '폼알데하이드' (X '포름알데히드')
  std_name            text NOT NULL,
  std_name_norm       text GENERATED ALWAYS AS (wq_normalize(std_name)) STORED,
  name_en             text,
  abbr                text,
  unit                text,                    -- 법령 표기 단위 (㎎/L, TU, 도, ℃ …)
  category            text NOT NULL,           -- 유기물 / 영양염류 / 중금속 / 미생물 …

  -- 법적 근거
  legal_basis         text,                    -- '물환경보전법 시행규칙 별표 13'
  legal_article       text,                    -- '제34조'
  legal_effective_from date,                   -- 해당 표기가 적용되는 시행일
  legal_revision      text,                    -- '개정 2025. 3. 20.'
  legal_status        text NOT NULL DEFAULT 'statutory'
                        CHECK (legal_status IN (
                          'statutory',      -- 현행 법정 항목
                          'superseded',     -- 과거 법정 항목 (구 데이터 호환용)
                          'non_statutory'   -- 법정 배출기준은 아니나 실제 관측되는 항목
                        )),
  -- 특정수질유해물질 여부. 목록의 정본은 별표 13이 아니라 '별표 3'이다.
  is_toxic_substance  boolean,
  toxic_substance_basis text,                  -- '물환경보전법 시행규칙 별표 3 제1호' 등
  source_url          text,                    -- 근거 원문 위치

  -- 검수 (초안 엑셀의 '검수상태/검수자' 칸을 그대로 옮긴 것)
  review_status       text NOT NULL DEFAULT 'draft'
                        CHECK (review_status IN ('draft','verified','rejected')),
  reviewed_by         text,
  reviewed_at         timestamptz,
  note                text,

  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);

-- 같은 법령 표기가 두 코드에 중복 등록되는 것을 막는다.
CREATE UNIQUE INDEX measurement_terms_std_name_norm_key
  ON measurement_terms (std_name_norm);

CREATE INDEX measurement_terms_category_idx ON measurement_terms (category);
CREATE INDEX measurement_terms_status_idx   ON measurement_terms (legal_status);

CREATE TRIGGER measurement_terms_set_updated_at
  BEFORE UPDATE ON measurement_terms
  FOR EACH ROW EXECUTE FUNCTION wq_set_updated_at();

COMMENT ON TABLE  measurement_terms IS '수질 측정항목 표준사전. 표준명은 법령 원문 표기를 따른다.';
COMMENT ON COLUMN measurement_terms.legal_status IS
  'statutory=현행 법정, superseded=과거 법정(구 데이터 호환), non_statutory=법정 배출기준 외 관측항목';

-- ---------------------------------------------------------------------------
-- 2. metadata_terms — 관측 메타 사전 (공공데이터 표준 근거)
-- ---------------------------------------------------------------------------
CREATE TABLE metadata_terms (
  code                text PRIMARY KEY
                        CHECK (code ~ '^MD-[0-9]{3}$'),

  std_name            text NOT NULL,
  std_name_norm       text GENERATED ALWAYS AS (wq_normalize(std_name)) STORED,
  name_en             text,
  abbr                text,                    -- 공통표준 영문약어 (NM, CD, YMD …)
  std_domain          text,                    -- 공통표준도메인 (명, 코드, 일자 …)
  value_type          text NOT NULL
                        CHECK (value_type IN ('text','code','integer','numeric',
                                              'date','timestamp','geo','boolean')),
  facet               text NOT NULL            -- 이 메타가 관측의 어느 축인지
                        CHECK (facet IN ('station','time','space','organization',
                                         'sampling','quality','record')),
  standard_basis      text,                    -- '공공데이터 공통표준용어' 등
  source_url          text,

  -- 정규화 규칙: 소스마다 다른 표현을 무엇으로 통일할지
  canonical_format    text,                    -- 'YYYY-MM-DD', 'WGS84 십진도' …
  normalization_note  text,                    -- 도분초→십진도 변환 필요 등

  review_status       text NOT NULL DEFAULT 'draft'
                        CHECK (review_status IN ('draft','verified','rejected')),
  reviewed_by         text,
  reviewed_at         timestamptz,
  note                text,

  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX metadata_terms_std_name_norm_key
  ON metadata_terms (std_name_norm);

CREATE INDEX metadata_terms_facet_idx ON metadata_terms (facet);

CREATE TRIGGER metadata_terms_set_updated_at
  BEFORE UPDATE ON metadata_terms
  FOR EACH ROW EXECUTE FUNCTION wq_set_updated_at();

COMMENT ON TABLE metadata_terms IS
  '관측 메타(측정소·측정일시·위치·기관) 표준사전. 측정값이 아니라 측정의 맥락을 가리키는 용어.';

-- ---------------------------------------------------------------------------
-- 3. term_sources — 출처 레지스트리
-- ---------------------------------------------------------------------------
CREATE TABLE term_sources (
  source_id           text PRIMARY KEY,        -- 'NIER_WQ_API', 'SEOUL_WPOS' …
  source_name         text NOT NULL,
  organization        text,
  source_type         text NOT NULL
                        CHECK (source_type IN ('api','file','spec','legal','manual')),
  base_url            text,
  access_note         text,                    -- 인증키 필요, CP949 인코딩 등
  encoding            text,
  reliability         text NOT NULL DEFAULT 'observed'
                        CHECK (reliability IN (
                          'legal',      -- 법령 원문
                          'standard',   -- 정부 표준 문서
                          'observed',   -- 실제 데이터에서 관측
                          'spec',       -- 기관 공식 명세 문서
                          'inferred'    -- 사람/AI 추정 — 확인 전
                        )),
  created_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON COLUMN term_sources.reliability IS
  '증거의 강도. legal/standard/observed/spec은 근거로 인용 가능, inferred는 검수 전까지 인용 금지.';

-- ---------------------------------------------------------------------------
-- 4. term_synonyms — 동의어. 1행 = 1개 표기 × 1개 출처.
-- ---------------------------------------------------------------------------
CREATE TABLE term_synonyms (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

  -- 두 사전 중 정확히 하나를 가리킨다 (실제 FK로 무결성 보장)
  measurement_code    text REFERENCES measurement_terms(code)
                        ON UPDATE CASCADE ON DELETE CASCADE,
  metadata_code       text REFERENCES metadata_terms(code)
                        ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT term_synonyms_exactly_one_parent
    CHECK (num_nonnulls(measurement_code, metadata_code) = 1),

  term_kind           text GENERATED ALWAYS AS
                        (CASE WHEN measurement_code IS NOT NULL
                              THEN 'measurement' ELSE 'metadata' END) STORED,

  surface             text NOT NULL,           -- 원문 그대로의 표기. 절대 손대지 않는다.
  surface_norm        text GENERATED ALWAYS AS (wq_normalize(surface)) STORED,

  -- 요구사항의 핵심: 동의어마다 출처와 수집일
  source_id           text NOT NULL REFERENCES term_sources(source_id)
                        ON UPDATE CASCADE,
  collected_on        date NOT NULL,
  evidence_url        text,                    -- 이 표기를 실제로 본 위치
  evidence_snippet    text,                    -- 헤더 한 줄, JSON 조각 등

  synonym_type        text NOT NULL DEFAULT 'column_name'
                        CHECK (synonym_type IN (
                          'column_name',   -- 실제 데이터의 컬럼/필드명
                          'legal_variant', -- 같은 법령 안의 다른 표기
                          'abbreviation',  -- 약어
                          'colloquial',    -- 현장 구어 (비오디 등)
                          'typo',          -- 오타. 실제로 유통되므로 사전에 남긴다.
                          'deprecated_std_name'  -- 표제어가 교체되어 강등된 구 표준명
                        )),
  review_status       text NOT NULL DEFAULT 'draft'
                        CHECK (review_status IN ('draft','verified','rejected')),
  reviewed_by         text,
  reviewed_at         timestamptz,
  note                text,

  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);

-- 같은 출처에서 같은 표기를 두 번 등록하지 않는다.
CREATE UNIQUE INDEX term_synonyms_unique_surface_per_source
  ON term_synonyms (surface_norm, source_id,
                    coalesce(measurement_code, ''), coalesce(metadata_code, ''));

-- 매칭의 주력 인덱스
CREATE INDEX term_synonyms_surface_norm_idx ON term_synonyms (surface_norm);
CREATE INDEX term_synonyms_trgm_idx
  ON term_synonyms USING gin (surface_norm gin_trgm_ops);
CREATE INDEX term_synonyms_source_idx ON term_synonyms (source_id, collected_on);

CREATE TRIGGER term_synonyms_set_updated_at
  BEFORE UPDATE ON term_synonyms
  FOR EACH ROW EXECUTE FUNCTION wq_set_updated_at();

-- 같은 정규화 표기가 서로 다른 표준코드에 붙으면 사전이 모순된다.
-- 막지는 않되(과거 데이터에 실제로 있을 수 있으므로) 조회로 감시한다. → v_synonym_conflicts
COMMENT ON TABLE term_synonyms IS
  '동의어 1건 = 1행. 같은 표기라도 출처가 다르면 별도 행 — 어느 기관이 언제 그렇게 쓰는지가 증거다.';

-- ---------------------------------------------------------------------------
-- 5. unresolved_columns — 사전이 자라는 입구
--    수집기가 새 데이터셋을 읽다 매칭 실패한 컬럼을 여기에 쌓는다.
--    사람이 확인해 term_synonyms로 승격하면 다음부터는 자동 매칭된다.
-- ---------------------------------------------------------------------------
CREATE TABLE unresolved_columns (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  surface             text NOT NULL,
  surface_norm        text GENERATED ALWAYS AS (wq_normalize(surface)) STORED,
  source_id           text REFERENCES term_sources(source_id) ON UPDATE CASCADE,
  dataset_name        text,
  evidence_url        text,
  sample_values       text[],                  -- 값 예시. 단위·형식 추론에 쓴다.
  first_seen_on       date NOT NULL DEFAULT current_date,
  last_seen_on        date NOT NULL DEFAULT current_date,
  seen_count          integer NOT NULL DEFAULT 1,

  suggested_code      text,                    -- 유사도/LLM이 제안한 표준코드
  suggested_by        text,                    -- 'trigram', 'llm:claude', '박서연'
  suggested_score     numeric(4,3),

  status              text NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','promoted','rejected','ignored')),
  resolved_by         text,
  resolved_at         timestamptz,
  note                text
);

CREATE UNIQUE INDEX unresolved_columns_unique
  ON unresolved_columns (surface_norm, coalesce(source_id, ''));
CREATE INDEX unresolved_columns_status_idx ON unresolved_columns (status, seen_count DESC);

COMMENT ON TABLE unresolved_columns IS
  '매칭 실패 큐. 여기 쌓인 것을 사람이 승인하면 term_synonyms로 옮겨가고 사전이 성장한다.';

-- ---------------------------------------------------------------------------
-- 6. 뷰
-- ---------------------------------------------------------------------------

-- 사람이 훑어보는 형태 — 초안 엑셀의 파이프 구분 컬럼을 그대로 재현한다.
CREATE VIEW v_dictionary_flat AS
SELECT
  m.code,
  'measurement'                       AS term_kind,
  m.std_name,
  m.name_en,
  m.abbr,
  m.unit,
  m.category,
  m.legal_basis,
  m.legal_status,
  string_agg(DISTINCT s.surface, '|' ORDER BY s.surface) AS synonyms,
  count(s.id)                         AS synonym_count,
  count(DISTINCT s.source_id)         AS source_count,
  max(s.collected_on)                 AS last_collected_on,
  m.review_status
FROM measurement_terms m
LEFT JOIN term_synonyms s ON s.measurement_code = m.code
                         AND s.review_status <> 'rejected'
GROUP BY m.code
UNION ALL
SELECT
  d.code,
  'metadata',
  d.std_name,
  d.name_en,
  d.abbr,
  NULL::text,                         -- metadata에는 단위 개념이 없다
  d.facet,
  d.standard_basis,
  NULL::text,                         -- metadata에는 legal_status가 없다
  string_agg(DISTINCT s.surface, '|' ORDER BY s.surface),
  count(s.id),
  count(DISTINCT s.source_id),
  max(s.collected_on),
  d.review_status
FROM metadata_terms d
LEFT JOIN term_synonyms s ON s.metadata_code = d.code
                         AND s.review_status <> 'rejected'
GROUP BY d.code;

-- 같은 표기가 두 개 이상의 표준코드에 붙은 경우 = 사전의 모순. 정기적으로 확인할 것.
CREATE VIEW v_synonym_conflicts AS
SELECT
  surface_norm,
  array_agg(DISTINCT coalesce(measurement_code, metadata_code)) AS codes,
  array_agg(DISTINCT surface)                                   AS surfaces,
  array_agg(DISTINCT source_id)                                 AS sources
FROM term_synonyms
WHERE review_status <> 'rejected'
GROUP BY surface_norm
HAVING count(DISTINCT coalesce(measurement_code, metadata_code)) > 1;

-- 소스별 커버리지: 어느 기관 데이터를 얼마나 소화하고 있는지
CREATE VIEW v_source_coverage AS
SELECT
  src.source_id,
  src.source_name,
  src.reliability,
  count(*) FILTER (WHERE s.term_kind = 'measurement') AS measurement_synonyms,
  count(*) FILTER (WHERE s.term_kind = 'metadata')    AS metadata_synonyms,
  min(s.collected_on)                                 AS first_collected,
  max(s.collected_on)                                 AS last_collected
FROM term_sources src
LEFT JOIN term_synonyms s ON s.source_id = src.source_id
GROUP BY src.source_id, src.source_name, src.reliability;

-- ---------------------------------------------------------------------------
-- 7. 매칭 함수 — 들어온 컬럼명 하나를 표준코드로 해석한다.
--    1순위 표준명 정확일치 → 2순위 동의어 정확일치 → 3순위 트라이그램 유사도
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION wq_match_column(
  p_surface      text,
  p_min_score    numeric DEFAULT 0.45,
  p_limit        integer DEFAULT 5
)
RETURNS TABLE (
  code           text,
  term_kind      text,
  std_name       text,
  match_type     text,
  score          numeric,
  via_surface    text,
  via_source     text
)
LANGUAGE sql STABLE
AS $$
WITH q AS (
  SELECT wq_normalize(p_surface) AS k
),
candidates AS (
  -- 1. 표준명 정확일치
  SELECT m.code, 'measurement'::text AS term_kind, m.std_name,
         'exact_standard'::text AS match_type, 1.000::numeric AS score,
         m.std_name AS via_surface, NULL::text AS via_source
  FROM measurement_terms m CROSS JOIN q
  WHERE m.std_name_norm = q.k

  UNION ALL

  SELECT d.code, 'metadata'::text, d.std_name,
         'exact_standard'::text, 1.000::numeric,
         d.std_name, NULL::text
  FROM metadata_terms d CROSS JOIN q
  WHERE d.std_name_norm = q.k

  UNION ALL

  -- 2. 동의어 정확일치
  SELECT coalesce(s.measurement_code, s.metadata_code),
         s.term_kind,
         coalesce(m.std_name, d.std_name),
         'exact_synonym'::text, 0.950::numeric,
         s.surface, s.source_id
  FROM term_synonyms s
  JOIN q ON s.surface_norm = q.k
  LEFT JOIN measurement_terms m ON m.code = s.measurement_code
  LEFT JOIN metadata_terms   d ON d.code = s.metadata_code
  WHERE s.review_status <> 'rejected'

  UNION ALL

  -- 3. 유사도 폴백 — 자동 채택 금지, 사람 확인 대상
  SELECT coalesce(s.measurement_code, s.metadata_code),
         s.term_kind,
         coalesce(m.std_name, d.std_name),
         'fuzzy'::text,
         round(similarity(s.surface_norm, q.k)::numeric, 3),
         s.surface, s.source_id
  FROM term_synonyms s
  CROSS JOIN q
  LEFT JOIN measurement_terms m ON m.code = s.measurement_code
  LEFT JOIN metadata_terms   d ON d.code = s.metadata_code
  WHERE s.review_status <> 'rejected'
    AND similarity(s.surface_norm, q.k) >= p_min_score
),
-- 같은 표준코드가 여러 경로로 잡히면 가장 강한 근거만 남긴다
best AS (
  SELECT DISTINCT ON (code) *
  FROM candidates
  ORDER BY code, score DESC, match_type
)
SELECT code, term_kind, std_name, match_type, score, via_surface, via_source
FROM best
ORDER BY score DESC, code
LIMIT p_limit;
$$;

COMMENT ON FUNCTION wq_match_column(text, numeric, integer) IS
  '컬럼명 → 표준코드 후보. exact_*는 자동 채택 가능, fuzzy는 사람 확인 후 term_synonyms에 추가할 것.';

-- 매칭 실패분을 큐에 적재 (있으면 카운트만 올린다)
CREATE OR REPLACE FUNCTION wq_record_unresolved(
  p_surface      text,
  p_source_id    text DEFAULT NULL,
  p_dataset      text DEFAULT NULL,
  p_evidence_url text DEFAULT NULL
) RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE v_id bigint;
BEGIN
  INSERT INTO unresolved_columns (surface, source_id, dataset_name, evidence_url)
  VALUES (p_surface, p_source_id, p_dataset, p_evidence_url)
  ON CONFLICT (surface_norm, coalesce(source_id, '')) DO UPDATE
    SET last_seen_on = current_date,
        seen_count   = unresolved_columns.seen_count + 1
  RETURNING id INTO v_id;
  RETURN v_id;
END;
$$;

-- 큐의 한 건을 동의어로 승격 (사전이 자라는 지점)
CREATE OR REPLACE FUNCTION wq_promote_unresolved(
  p_id        bigint,
  p_code      text,
  p_reviewer  text
) RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
  v_row unresolved_columns%ROWTYPE;
  v_new bigint;
BEGIN
  SELECT * INTO v_row FROM unresolved_columns WHERE id = p_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'unresolved_columns id=% 없음', p_id;
  END IF;

  INSERT INTO term_synonyms (
    measurement_code, metadata_code, surface, source_id, collected_on,
    evidence_url, synonym_type, review_status, reviewed_by, reviewed_at
  ) VALUES (
    CASE WHEN p_code LIKE 'WQ-%' THEN p_code END,
    CASE WHEN p_code LIKE 'MD-%' THEN p_code END,
    v_row.surface,
    coalesce(v_row.source_id, 'MANUAL'),
    v_row.first_seen_on,
    v_row.evidence_url,
    'column_name',
    'verified', p_reviewer, now()
  )
  RETURNING id INTO v_new;

  UPDATE unresolved_columns
     SET status = 'promoted', resolved_by = p_reviewer, resolved_at = now()
   WHERE id = p_id;

  RETURN v_new;
END;
$$;

COMMIT;

-- ============================================================================
-- 사용 예시
-- ============================================================================
-- 1) 새 데이터셋의 컬럼 해석
--      SELECT * FROM wq_match_column('생물학적 산소요구량');
--      SELECT * FROM wq_match_column('TOT_N');
--      SELECT * FROM wq_match_column('총소질소');      -- 오타도 사전에 있으면 잡힌다
--
-- 2) 매칭 실패분 적재 후 검토
--      SELECT wq_record_unresolved('BOD농도(mg/l)', 'DATAGO_FILE', '○○시 하천수질');
--      SELECT * FROM unresolved_columns WHERE status='pending' ORDER BY seen_count DESC;
--      SELECT wq_promote_unresolved(1, 'WQ-001', '박서연');
--
-- 3) 사람이 보는 사전 (엑셀과 같은 파이프 형태)
--      SELECT * FROM v_dictionary_flat ORDER BY term_kind, code;
--
-- 4) 건강검진
--      SELECT * FROM v_synonym_conflicts;   -- 한 표기가 두 코드에 붙었는가
--      SELECT * FROM v_source_coverage;     -- 어느 소스를 얼마나 흡수했는가
--      SELECT count(*) FROM measurement_terms WHERE review_status='draft';
