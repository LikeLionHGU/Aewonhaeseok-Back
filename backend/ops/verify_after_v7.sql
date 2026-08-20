-- V7 배포 전후 데이터 검증용 읽기 전용 SQL.
-- 이 파일은 DELETE/UPDATE를 실행하지 않는다. 실제 정리는 Flyway V7이 트랜잭션으로 수행한다.

-- 1) 한 파일에 여러 매핑 회차의 측정값이 섞였는지 확인
SELECT file_id,
       COUNT(*) AS measurement_count,
       COUNT(DISTINCT mapping_run_id) AS mapping_run_count
  FROM measurements
 GROUP BY file_id
HAVING COUNT(DISTINCT mapping_run_id) > 1;

-- 2) 원본 위치 기준 중복 확인. V7 이후 결과가 0행이어야 한다.
SELECT file_id, source_row, source_column_index, COUNT(*) AS duplicate_count
  FROM measurements
 GROUP BY file_id, source_row, source_column_index
HAVING COUNT(*) > 1;

-- 3) 파일별 적재 이력 중복 확인. V7 이후 결과가 0행이어야 한다.
SELECT file_id, COUNT(*) AS ingestion_run_count
  FROM ingestion_runs
 GROUP BY file_id
HAVING COUNT(*) > 1;

-- 4) 같은 파일/열의 검토 항목 중복 확인. V7 이후 결과가 0행이어야 한다.
SELECT file_id, source_column_index, raw, COUNT(*) AS review_count
  FROM review_items
 GROUP BY file_id, source_column_index, raw
HAVING COUNT(*) > 1;

-- 5) 기준치 검증 상태. 현행 CSV 동기화 후 demo_count=0이어야 한다.
SELECT source, COUNT(*) AS row_count
  FROM standard_limits
 GROUP BY source;

-- 6) 규모별 일반 기준이 모두 있는지 확인(BOD/TOC/SS: 지역 4 × 규모 2)
SELECT item_code, scale, COUNT(*) AS region_count
  FROM standard_limits
 WHERE item_code IN ('WQ-001', 'WQ-002', 'WQ-004')
 GROUP BY item_code, scale
 ORDER BY item_code, scale;
