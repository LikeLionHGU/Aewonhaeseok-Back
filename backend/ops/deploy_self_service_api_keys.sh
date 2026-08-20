#!/usr/bin/env bash
set -Eeuo pipefail

env_file=/etc/awon/awon.env
new_jar=/tmp/awon-backend-self-key.jar
app_jar=/opt/awon/app/awon-backend.jar
backup_dir="/var/backups/awon/self-key-$(date +%Y%m%d-%H%M%S)"

[[ -s "$new_jar" ]]
[[ -s "$app_jar" ]]
install -d -m 0700 "$backup_dir"
set -a
source "$env_file"
set +a

mysqldump --single-transaction --routines --triggers --no-tablespaces \
  -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" \
  | gzip -9 > "$backup_dir/awon-before-self-key.sql.gz"
gzip -t "$backup_dir/awon-before-self-key.sql.gz"
[[ "$(gzip -dc "$backup_dir/awon-before-self-key.sql.gz" | wc -c)" -gt 1000 ]]
cp "$app_jar" "$backup_dir/awon-backend-before-self-key.jar"
sha256sum "$backup_dir"/*.gz "$backup_dir"/*.jar > "$backup_dir/SHA256SUMS"

rollback() {
  echo "DEPLOY_FAILED_ROLLING_BACK" >&2
  install -o awon -g awon -m 0644 "$backup_dir/awon-backend-before-self-key.jar" "$app_jar"
  systemctl restart awon-api
}
trap rollback ERR

systemctl stop awon-api
install -o awon -g awon -m 0644 "$new_jar" "$app_jar"
systemctl start awon-api

ready=false
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8080/v3/api-docs >/dev/null; then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == true ]]

migration="$(mysql -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -Nse \
  "SELECT CONCAT(version, ':', success) FROM flyway_schema_history WHERE version='10'")"
[[ "$migration" == "10:1" ]]

owner_column="$(mysql -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -Nse \
  "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='${DB_NAME}' AND table_name='organizations' AND column_name='owner_user_id'")"
[[ "$owner_column" == "1" ]]

unauthorized_status="$(curl -sS -o /tmp/awon-self-key-unauthorized.json -w '%{http_code}' \
  http://127.0.0.1:8080/api/v1/open-api/keys)"
[[ "$unauthorized_status" == "401" ]]
grep -q 'AUTH_REQUIRED' /tmp/awon-self-key-unauthorized.json
rm -f /tmp/awon-self-key-unauthorized.json

systemctl is-active --quiet awon-api
trap - ERR

echo "BACKUP_DIR=$backup_dir"
echo "FLYWAY_V10=$migration"
echo "OWNER_COLUMN=$owner_column"
echo "UNAUTHENTICATED_KEYS=$unauthorized_status"
echo "SELF_SERVICE_API_KEYS_DEPLOYED"
