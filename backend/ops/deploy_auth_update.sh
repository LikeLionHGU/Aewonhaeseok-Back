#!/usr/bin/env bash
set -Eeuo pipefail

backup_dir=/var/backups/awon/auth-20260819
env_file=/etc/awon/awon.env
new_jar=/tmp/awon-backend-auth.jar
app_jar=/opt/awon/app/awon-backend.jar

[[ -s "$new_jar" ]] || { echo "new jar missing" >&2; exit 1; }
install -d -m 0700 "$backup_dir"

set -a
source "$env_file"
set +a

mysqldump --single-transaction --routines --triggers --no-tablespaces \
  -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" \
  | gzip -9 > "$backup_dir/awon-before-auth.sql.gz.new"
gzip -t "$backup_dir/awon-before-auth.sql.gz.new"
uncompressed_size="$(gzip -dc "$backup_dir/awon-before-auth.sql.gz.new" | wc -c)"
[[ "$uncompressed_size" -gt 1000 ]] || { echo "database backup is unexpectedly small" >&2; exit 1; }
mv "$backup_dir/awon-before-auth.sql.gz.new" "$backup_dir/awon-before-auth.sql.gz"

if [[ ! -s "$backup_dir/awon-backend-before-auth.jar" ]]; then
  cp "$app_jar" "$backup_dir/awon-backend-before-auth.jar"
fi
sha256sum "$backup_dir/awon-before-auth.sql.gz" \
  "$backup_dir/awon-backend-before-auth.jar" > "$backup_dir/SHA256SUMS"

set_env() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "$env_file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$env_file"
  fi
}

if grep -q '^JWT_SECRET=' "$env_file"; then
  jwt_secret="$(sed -n 's/^JWT_SECRET=//p' "$env_file")"
else
  jwt_secret="$(openssl rand -hex 48)"
fi
set_env JWT_SECRET "$jwt_secret"
set_env AUTH_REQUIRED false
set_env AUTH_COOKIE_SECURE true
set_env AUTH_COOKIE_SAME_SITE Strict
set_env CORS_ALLOWED_ORIGINS "http://localhost:5173,http://localhost:3000,http://1.201.116.24,https://wanna-ask-me.aewonhaeseo.deno.net"

credentials_file=/etc/awon/legacy-admin-credentials
if [[ ! -s "$credentials_file" ]]; then
  admin_password="$(openssl rand -base64 30 | tr -d '/+=')"
  printf 'email=legacy-admin@aewonhaeseo.local\npassword=%s\n' "$admin_password" > "$credentials_file"
  chmod 0600 "$credentials_file"
else
  admin_password="$(sed -n 's/^password=//p' "$credentials_file")"
fi
set_env BOOTSTRAP_ADMIN_PASSWORD "$admin_password"
chmod 0600 "$env_file"

systemctl stop awon-api
install -o awon -g awon -m 0644 "$new_jar" "$app_jar"
if ! systemctl start awon-api; then
  install -o awon -g awon -m 0644 "$backup_dir/awon-backend-before-auth.jar" "$app_jar"
  systemctl start awon-api
  exit 1
fi

ready=false
for _ in $(seq 1 45); do
  if curl --fail --silent http://127.0.0.1:8080/api/v1/standards >/dev/null; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  journalctl -u awon-api -n 100 --no-pager
  install -o awon -g awon -m 0644 "$backup_dir/awon-backend-before-auth.jar" "$app_jar"
  systemctl restart awon-api
  exit 1
fi

# 최초 관리자 암호가 DB에 해시된 뒤 평문을 서비스 환경에서 제거한다.
sed -i '/^BOOTSTRAP_ADMIN_PASSWORD=/d' "$env_file"

source "$env_file"
mysql -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" -N -e \
  "SELECT CONCAT('users=', COUNT(*)) FROM ${DB_NAME}.app_users;
   SELECT CONCAT('owned_files=', COUNT(*)) FROM ${DB_NAME}.files WHERE owner_user_id=1;
   SELECT CONCAT('owned_analyses=', COUNT(*)) FROM ${DB_NAME}.analysis_runs WHERE owner_user_id=1;"
systemctl is-active awon-api awon-mapper nginx mysql
echo "ADMIN_CREDENTIALS=$credentials_file"
echo "AUTH_DEPLOYED"
