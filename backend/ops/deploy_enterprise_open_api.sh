#!/usr/bin/env bash
set -Eeuo pipefail

env_file=/etc/awon/awon.env
new_jar=/tmp/awon-backend-open-api.jar
app_jar=/opt/awon/app/awon-backend.jar
backup_dir=/var/backups/awon/open-api-20260821

[[ -s "$new_jar" ]]
install -d -m 0700 "$backup_dir"
set -a; source "$env_file"; set +a

mysqldump --single-transaction --routines --triggers --no-tablespaces \
  -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" | gzip -9 > "$backup_dir/awon-before-open-api.sql.gz"
gzip -t "$backup_dir/awon-before-open-api.sql.gz"
[[ "$(gzip -dc "$backup_dir/awon-before-open-api.sql.gz" | wc -c)" -gt 1000 ]]
cp "$app_jar" "$backup_dir/awon-backend-before-open-api.jar"
sha256sum "$backup_dir"/*.gz "$backup_dir"/*.jar > "$backup_dir/SHA256SUMS"

systemctl stop awon-api
install -o awon -g awon -m 0644 "$new_jar" "$app_jar"
systemctl start awon-api

ready=false
for _ in $(seq 1 45); do
  if curl -fsS http://127.0.0.1:8080/v3/api-docs/enterprise-open-api >/dev/null; then ready=true; break; fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  journalctl -u awon-api -n 120 --no-pager
  install -o awon -g awon -m 0644 "$backup_dir/awon-backend-before-open-api.jar" "$app_jar"
  systemctl restart awon-api
  exit 1
fi

status="$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/open-api/v1/me)"
[[ "$status" == 401 ]]
systemctl is-active awon-api awon-mapper nginx mysql
echo "OPEN_API_WITHOUT_KEY=$status"
echo "OPEN_API_DEPLOYED"
