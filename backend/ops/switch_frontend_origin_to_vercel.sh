#!/usr/bin/env bash
set -Eeuo pipefail

env_file=/etc/awon/awon.env
origin=https://aewonhaeseo-front.vercel.app
origins="http://localhost:5173,http://localhost:3000,http://1.201.116.24,https://1-201-116-24.sslip.io,${origin}"
backup_file="/var/backups/awon/awon.env-before-vercel-cors-$(date +%Y%m%d-%H%M%S)"

install -d -m 0700 /var/backups/awon
cp -p "$env_file" "$backup_file"

rollback() {
  cp -p "$backup_file" "$env_file"
  systemctl restart awon-api
}
trap rollback ERR

grep -q '^CORS_ALLOWED_ORIGINS=' "$env_file"
sed -i "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=${origins}|" "$env_file"
systemctl restart awon-api

ready=false
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8080/v3/api-docs >/dev/null; then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == true ]]

cors_headers="$(mktemp)"
trap 'rm -f "$cors_headers"' EXIT
status="$(curl -sS -D "$cors_headers" -o /dev/null -w '%{http_code}' -X OPTIONS \
  http://127.0.0.1:8080/api/v1/auth/me \
  -H "Origin: $origin" \
  -H 'Access-Control-Request-Method: GET')"
[[ "$status" == "200" ]]
grep -qi "^Access-Control-Allow-Origin: ${origin}" "$cors_headers"

trap - ERR
echo "BACKUP_FILE=$backup_file"
echo "CORS_ORIGIN=$origin"
echo "CORS_PREFLIGHT=$status"
echo "VERCEL_FRONTEND_ORIGIN_ALLOWED"
