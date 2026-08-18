ALTER TABLE analysis_runs
    ADD COLUMN assumptions JSON NULL AFTER conditions,
    ADD COLUMN series JSON NULL AFTER assumptions,
    ADD COLUMN limits JSON NULL AFTER series,
    ADD COLUMN scale VARCHAR(20) NULL AFTER region_grade;
