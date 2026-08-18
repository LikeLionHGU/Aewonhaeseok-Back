-- 재매핑·재수집 멱등성 보강.
-- 애플리케이션도 파일 단위 교체/검토 재사용을 수행하지만 DB 제약으로 한 번 더 막는다.

ALTER TABLE measurements
    ADD COLUMN source_column_index INT NULL AFTER source_column;

UPDATE measurements m
  JOIN mapping_columns c
    ON c.mapping_run_id = m.mapping_run_id
   AND c.raw = m.source_column
   SET m.source_column_index = c.column_index;

-- 파일별로 실제 적재된 가장 최신 매핑 회차만 남긴다.
DELETE m
  FROM measurements m
  JOIN mapping_runs current_run ON current_run.id = m.mapping_run_id
  JOIN mapping_runs newer_run
    ON newer_run.file_id = current_run.file_id
   AND newer_run.round_no > current_run.round_no
  JOIN measurements newer_measurement ON newer_measurement.mapping_run_id = newer_run.id;

ALTER TABLE measurements
    MODIFY source_column_index INT NOT NULL,
    ADD UNIQUE KEY uk_measurements_file_source (file_id, source_row, source_column_index);

-- 적재 이력도 파일마다 현재 상태 한 건만 유지한다.
DELETE ir
  FROM ingestion_runs ir
  JOIN mapping_runs current_run ON current_run.id = ir.mapping_run_id
  JOIN mapping_runs newer_run
    ON newer_run.file_id = current_run.file_id
   AND newer_run.round_no > current_run.round_no
  JOIN ingestion_runs newer_ingestion ON newer_ingestion.mapping_run_id = newer_run.id;

ALTER TABLE ingestion_runs
    ADD UNIQUE KEY uk_ingestion_file (file_id);

-- 같은 파일의 같은 열에서 재매핑 때 생긴 검토 항목은 하나로 합친다.
-- 사람이 판정한 항목을 우선하고 동일 상태끼리는 최신 항목을 남긴다.
ALTER TABLE review_items
    ADD COLUMN source_column_index INT NULL AFTER raw;

UPDATE review_items r
  JOIN mapping_columns c ON c.id = r.mapping_column_id
   SET r.source_column_index = c.column_index;

DELETE loser
  FROM review_items loser
  JOIN review_items winner
    ON winner.file_id = loser.file_id
   AND winner.raw = loser.raw
   AND winner.source_column_index = loser.source_column_index
   AND winner.id <> loser.id
   AND (
       (winner.verdict IS NOT NULL AND loser.verdict IS NULL)
       OR ((winner.verdict IS NULL) = (loser.verdict IS NULL) AND winner.id > loser.id)
   );

ALTER TABLE review_items
    MODIFY source_column_index INT NOT NULL,
    ADD UNIQUE KEY uk_review_file_column (file_id, source_column_index, raw);
