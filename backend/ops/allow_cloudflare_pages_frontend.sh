#!/usr/bin/env bash
set -Eeuo pipefail

env_file=/etc/awon/awon.env
origin=https://aewonhaeseo-front.pages.dev
backup_file="/var/backups/awon/awon.env-before-pages-cors-$(date +%Y%m%d-%H%M%S)"

install -d -m 0700 /var/backups/awon
cp -p "$env_file" "$backup_file"

rollback() {
  cp -p "$backup_file" "$env_file"
  systemctl restart awon-api
}
trap rollback ERR

current="$(sed -n 's/^CORS_ALLOWED_ORIGINS=//p' "$env_file")"
[[ -n "$current" ]]
case ",$current," in
  *",$origin,"*) ;;
  *) sed -i "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=${current},${origin}|" "$env_file" ;;
esac

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
echo "CLOUDFLARE_PAGES_ORIGIN_ALLOWED"
