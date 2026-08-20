#!/usr/bin/env bash
set -Eeuo pipefail

target_email=legacy-admin@aewonhaeseo.local
env_file=/etc/awon/awon.env
backup_dir="/var/backups/awon/admin-data-purge-$(date +%Y%m%d-%H%M%S)"
path_list="$(mktemp)"
resolved_list="$(mktemp)"
api_stopped=false

cleanup() {
  rm -f "$path_list" "$resolved_list"
  if [[ "$api_stopped" == true ]]; then
    systemctl start awon-api || true
  fi
}
trap cleanup EXIT

set -a
source "$env_file"
set +a

user_id="$(mysql -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -Nse \
  "SELECT id FROM app_users WHERE email='${target_email}'")"
user_role="$(mysql -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -Nse \
  "SELECT role FROM app_users WHERE email='${target_email}'")"
[[ -n "$user_id" ]]
[[ "$user_role" == "ADMIN" ]]

storage_root="$(realpath -m "$STORAGE_ROOT")"
allowed_root="$storage_root"

install -d -m 0700 "$backup_dir/files"

mysqldump --single-transaction --routines --triggers --no-tablespaces \
  -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" \
  | gzip -9 > "$backup_dir/awon-before-admin-data-purge.sql.gz"
gzip -t "$backup_dir/awon-before-admin-data-purge.sql.gz"
[[ "$(gzip -dc "$backup_dir/awon-before-admin-data-purge.sql.gz" | wc -c)" -gt 1000 ]]

mysql -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -Nse \
  "SELECT stored_path FROM files WHERE owner_user_id=${user_id} ORDER BY id" > "$path_list"

while IFS= read -r stored_path; do
  [[ -n "$stored_path" ]]
  resolved="$(realpath -m "$stored_path")"
  case "$resolved" in
    "$allowed_root"/*) ;;
    *) echo "UNSAFE_STORED_PATH=$resolved" >&2; exit 1 ;;
  esac
  printf '%s\n' "$resolved" >> "$resolved_list"
done < "$path_list"

systemctl stop awon-api
api_stopped=true

while IFS= read -r source_file; do
  if [[ -f "$source_file" ]]; then
    backup_file="$backup_dir/files/$(basename "$source_file")"
    cp -p -- "$source_file" "$backup_file"
    cmp -s -- "$source_file" "$backup_file"
  fi
done < "$resolved_list"

mysql -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" <<SQL
START TRANSACTION;
SET @user_id := (SELECT id FROM app_users WHERE email='${target_email}' FOR UPDATE);
DELETE FROM analysis_runs WHERE owner_user_id=@user_id;
DELETE FROM files WHERE owner_user_id=@user_id;
COMMIT;
SQL

while IFS= read -r source_file; do
  if [[ -f "$source_file" ]]; then
    rm -f -- "$source_file"
  fi
done < "$resolved_list"

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

mysql -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -Nse "
SET @user_id := (SELECT id FROM app_users WHERE email='${target_email}');
SELECT CONCAT('files=', COUNT(*)) FROM files WHERE owner_user_id=@user_id;
SELECT CONCAT('mapping_runs=', COUNT(*)) FROM mapping_runs mr JOIN files f ON f.id=mr.file_id WHERE f.owner_user_id=@user_id;
SELECT CONCAT('mapping_columns=', COUNT(*)) FROM mapping_columns mc JOIN mapping_runs mr ON mr.id=mc.mapping_run_id JOIN files f ON f.id=mr.file_id WHERE f.owner_user_id=@user_id;
SELECT CONCAT('review_items=', COUNT(*)) FROM review_items ri JOIN files f ON f.id=ri.file_id WHERE f.owner_user_id=@user_id;
SELECT CONCAT('measurements=', COUNT(*)) FROM measurements m JOIN files f ON f.id=m.file_id WHERE f.owner_user_id=@user_id;
SELECT CONCAT('ingestion_runs=', COUNT(*)) FROM ingestion_runs ir JOIN files f ON f.id=ir.file_id WHERE f.owner_user_id=@user_id;
SELECT CONCAT('analysis_runs=', COUNT(*)) FROM analysis_runs WHERE owner_user_id=@user_id;
"

sha256sum "$backup_dir/awon-before-admin-data-purge.sql.gz" "$backup_dir"/files/* \
  > "$backup_dir/SHA256SUMS" 2>/dev/null || sha256sum \
  "$backup_dir/awon-before-admin-data-purge.sql.gz" > "$backup_dir/SHA256SUMS"

systemctl is-active --quiet awon-api
echo "BACKUP_DIR=$backup_dir"
echo "ADMIN_MAPPING_DATA_PURGED"
