START TRANSACTION;

-- 기존 영문 판정값을 현재 API의 표준 판정값으로 정규화한다.
UPDATE review_items
SET verdict = candidate_code
WHERE verdict IN ('approved', '승인')
  AND candidate_code IS NOT NULL;

UPDATE review_items
SET verdict = 'no_match'
WHERE verdict IN ('rejected', '기각');

-- 배포 및 프런트 감사 과정에서 생성한 분석 실행만 제거한다.
DELETE FROM analysis_runs
WHERE id BETWEEN 20 AND 26;

-- 프런트에서 삭제 요청한 테스트 파일만 정확히 제거한다.
DELETE FROM files
WHERE (id = 8 AND original_filename = 'audit.csv')
   OR (id = 9 AND original_filename = 'cross.csv')
   OR (id = 10 AND original_filename = 'low.csv');

-- 미결 항목이 하나도 없는 기존 reviewing 파일의 상태를 바로잡는다.
UPDATE files AS f
SET f.status = 'completed'
WHERE f.status = 'reviewing'
  AND EXISTS (
    SELECT 1 FROM mapping_runs AS mr WHERE mr.file_id = f.id
  )
  AND NOT EXISTS (
    SELECT 1
    FROM review_items AS ri
    WHERE ri.file_id = f.id
      AND ri.verdict IS NULL
  );

COMMIT;
