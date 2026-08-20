CREATE TABLE app_users (
    id BIGINT NOT NULL AUTO_INCREMENT,
    email VARCHAR(320) NOT NULL,
    password_hash VARCHAR(100) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'USER',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_app_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO app_users (id, email, password_hash, display_name, role, enabled, created_at)
VALUES (1, 'legacy-admin@aewonhaeseo.local', '{disabled}', '기존 데이터 관리자',
        'ADMIN', TRUE, CURRENT_TIMESTAMP(6));

ALTER TABLE files ADD COLUMN owner_user_id BIGINT NULL AFTER id;
UPDATE files SET owner_user_id = 1 WHERE owner_user_id IS NULL;
ALTER TABLE files
    MODIFY owner_user_id BIGINT NOT NULL,
    ADD KEY idx_files_owner_uploaded (owner_user_id, uploaded_at),
    ADD CONSTRAINT fk_files_owner FOREIGN KEY (owner_user_id) REFERENCES app_users (id);

ALTER TABLE analysis_runs ADD COLUMN owner_user_id BIGINT NULL AFTER id;
UPDATE analysis_runs SET owner_user_id = 1 WHERE owner_user_id IS NULL;
ALTER TABLE analysis_runs
    MODIFY owner_user_id BIGINT NOT NULL,
    ADD KEY idx_analysis_owner_ran (owner_user_id, ran_at),
    ADD CONSTRAINT fk_analysis_owner FOREIGN KEY (owner_user_id) REFERENCES app_users (id);
