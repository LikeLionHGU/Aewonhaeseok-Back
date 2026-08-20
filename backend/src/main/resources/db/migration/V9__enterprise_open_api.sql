CREATE TABLE organizations (
    id BIGINT NOT NULL AUTO_INCREMENT,
    name VARCHAR(200) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_user_id BIGINT NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_organizations_name (name),
    CONSTRAINT fk_organizations_creator FOREIGN KEY (created_by_user_id) REFERENCES app_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE organization_api_keys (
    id BIGINT NOT NULL AUTO_INCREMENT,
    organization_id BIGINT NOT NULL,
    key_hash CHAR(64) NOT NULL,
    key_prefix VARCHAR(24) NOT NULL,
    key_name VARCHAR(100) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    requests_per_minute INT NOT NULL DEFAULT 60,
    last_used_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL,
    revoked_at DATETIME(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_organization_api_keys_hash (key_hash),
    KEY idx_organization_api_keys_org (organization_id, active),
    CONSTRAINT fk_organization_api_keys_org FOREIGN KEY (organization_id)
        REFERENCES organizations(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE organization_dictionary_terms (
    id BIGINT NOT NULL AUTO_INCREMENT,
    organization_id BIGINT NOT NULL,
    alias_raw VARCHAR(500) NOT NULL,
    alias_normalized VARCHAR(500) NOT NULL,
    standard_code VARCHAR(20) NOT NULL,
    note VARCHAR(1000) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_org_dictionary_alias (organization_id, alias_normalized),
    KEY idx_org_dictionary_code (organization_id, standard_code),
    CONSTRAINT fk_org_dictionary_org FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE open_api_usage_logs (
    id BIGINT NOT NULL AUTO_INCREMENT,
    api_key_id BIGINT NOT NULL,
    organization_id BIGINT NOT NULL,
    method VARCHAR(10) NOT NULL,
    path VARCHAR(500) NOT NULL,
    response_status INT NOT NULL,
    duration_ms INT NOT NULL,
    usage_units INT NOT NULL DEFAULT 1,
    requested_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    KEY idx_open_api_usage_org_time (organization_id, requested_at),
    KEY idx_open_api_usage_key_time (api_key_id, requested_at),
    CONSTRAINT fk_open_api_usage_key FOREIGN KEY (api_key_id) REFERENCES organization_api_keys(id),
    CONSTRAINT fk_open_api_usage_org FOREIGN KEY (organization_id) REFERENCES organizations(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
