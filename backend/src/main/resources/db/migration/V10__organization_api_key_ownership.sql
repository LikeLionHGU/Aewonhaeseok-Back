ALTER TABLE organizations
    ADD COLUMN owner_user_id BIGINT NULL AFTER created_by_user_id,
    ADD UNIQUE KEY uk_organizations_owner (owner_user_id),
    ADD CONSTRAINT fk_organizations_owner FOREIGN KEY (owner_user_id) REFERENCES app_users(id);
