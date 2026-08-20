#!/usr/bin/env bash
set -Eeuo pipefail

domain=1-201-116-24.sslip.io
nginx_config=/etc/nginx/sites-available/awon-api
env_file=/etc/awon/awon.env
backup_dir=/var/backups/awon/https-auth-20260819

install -d -m 0700 "$backup_dir"
cp "$nginx_config" "$backup_dir/awon-api.nginx.before"
cp "$env_file" "$backup_dir/awon.env.before"

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y certbot python3-certbot-nginx

sed -i "s/server_name _;/server_name ${domain} _;/" "$nginx_config"
nginx -t
systemctl reload nginx

certbot --nginx -d "$domain" --non-interactive --agree-tos \
  --register-unsafely-without-email --no-redirect

set_env() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "$env_file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$env_file"
  fi
}

set_env AUTH_REQUIRED true
set_env AUTH_COOKIE_SECURE true
set_env AUTH_COOKIE_SAME_SITE Strict
set_env CORS_ALLOWED_ORIGINS "http://localhost:5173,http://localhost:3000,http://1.201.116.24,https://wanna-ask-me.aewonhaeseo.deno.net,https://${domain}"
chmod 0600 "$env_file"

nginx -t
systemctl restart awon-api nginx

for _ in $(seq 1 45); do
  if curl --fail --silent http://127.0.0.1:8080/v3/api-docs >/dev/null; then
    break
  fi
  sleep 1
done

unauthenticated_status="$(curl -sS -o /dev/null -w '%{http_code}' \
  "https://${domain}/api/v1/files?size=1")"
[[ "$unauthenticated_status" == 401 ]]

certificate_expiry="$(openssl s_client -connect "${domain}:443" -servername "$domain" </dev/null 2>/dev/null \
  | openssl x509 -noout -enddate)"

systemctl is-active awon-api awon-mapper nginx mysql
echo "HTTPS_URL=https://${domain}"
echo "UNAUTHENTICATED_FILES_STATUS=${unauthenticated_status}"
echo "CERTIFICATE_${certificate_expiry}"
echo "HTTPS_AND_AUTH_ENABLED"
