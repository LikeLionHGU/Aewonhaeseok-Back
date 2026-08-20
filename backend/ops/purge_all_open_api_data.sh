#!/usr/bin/env bash
set -Eeuo pipefail

env_file=/etc/awon/awon.env
backup_dir="/var/backups/awon/open-api-data-purge-$(date +%Y%m%d-%H%M%S)"
api_stopped=false

cleanup() {
  if [[ "$api_stopped" == true ]]; then
    systemctl start awon-api || true
  fi
}
trap cleanup EXIT

set -a
source "$env_file"
set +a

install -d -m 0700 "$backup_dir"

mysqldump --single-transaction --routines --triggers --no-tablespaces \
  -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" \
  | gzip -9 > "$backup_dir/awon-before-open-api-data-purge.sql.gz"
gzip -t "$backup_dir/awon-before-open-api-data-purge.sql.gz"
[[ "$(gzip -dc "$backup_dir/awon-before-open-api-data-purge.sql.gz" | wc -c)" -gt 1000 ]]

mysql_cmd=(mysql -h "$DB_HOST" -P "$DB_PORT" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -Nse)

echo "BEFORE"
"${mysql_cmd[@]}" "
SELECT CONCAT('organizations=', COUNT(*)) FROM organizations;
SELECT CONCAT('api_keys=', COUNT(*)) FROM organization_api_keys;
SELECT CONCAT('organization_dictionary_terms=', COUNT(*)) FROM organization_dictionary_terms;
SELECT CONCAT('usage_logs=', COUNT(*)) FROM open_api_usage_logs;
SELECT CONCAT('app_users=', COUNT(*)) FROM app_users;
"

users_before="$("${mysql_cmd[@]}" "SELECT COUNT(*) FROM app_users")"

systemctl stop awon-api
api_stopped=true

mysql -h "$DB_HOST" -P "$DB_PORT" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" <<'SQL'
START TRANSACTION;
DELETE FROM open_api_usage_logs;
DELETE FROM organization_dictionary_terms;
DELETE FROM organization_api_keys;
DELETE FROM organizations;
COMMIT;
SQL

users_after="$("${mysql_cmd[@]}" "SELECT COUNT(*) FROM app_users")"
[[ "$users_before" == "$users_after" ]]

systemctl start awon-api
api_stopped=false

ready=false
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8080/v3/api-docs >/dev/null; then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == true ]]

echo "AFTER"
"${mysql_cmd[@]}" "
SELECT CONCAT('organizations=', COUNT(*)) FROM organizations;
SELECT CONCAT('api_keys=', COUNT(*)) FROM organization_api_keys;
SELECT CONCAT('organization_dictionary_terms=', COUNT(*)) FROM organization_dictionary_terms;
SELECT CONCAT('usage_logs=', COUNT(*)) FROM open_api_usage_logs;
SELECT CONCAT('app_users=', COUNT(*)) FROM app_users;
"

sha256sum "$backup_dir/awon-before-open-api-data-purge.sql.gz" > "$backup_dir/SHA256SUMS"
systemctl is-active --quiet awon-api

echo "BACKUP_DIR=$backup_dir"
echo "ALL_OPEN_API_DATA_PURGED"
