#!/usr/bin/env bash
set -Eeuo pipefail

web_base=http://127.0.0.1:8080/api/v1
open_base=http://127.0.0.1:8080/open-api/v1
admin_credentials=/etc/awon/legacy-admin-credentials
tmp=/tmp/awon-open-api-initial
mkdir -p "$tmp"; chmod 0700 "$tmp"
trap 'rm -rf "$tmp"' EXIT

email="$(sed -n 's/^email=//p' "$admin_credentials")"
password="$(sed -n 's/^password=//p' "$admin_credentials")"
login_payload="$(python3 -c 'import json,sys; print(json.dumps({"email":sys.argv[1],"password":sys.argv[2]}))' "$email" "$password")"
curl -fsS -D "$tmp/login.headers" -o /dev/null -H 'Content-Type: application/json' \
  -d "$login_payload" "$web_base/auth/login"
jwt="$(sed -n 's/^[Ss]et-[Cc]ookie: AWON_ACCESS_TOKEN=\([^;]*\).*/\1/p' "$tmp/login.headers" | tr -d '\r')"
[[ -n "$jwt" ]]

curl -fsS -o "$tmp/issued.json" -H "Cookie: AWON_ACCESS_TOKEN=$jwt" \
  -H 'Content-Type: application/json' \
  -d '{"name":"어원 Open API","key_name":"초기 운영 키","requests_per_minute":60}' \
  "$web_base/admin/open-api/organizations"
api_key="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["api_key"])' < "$tmp/issued.json")"
org_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["organization"]["id"])' < "$tmp/issued.json")"
[[ "$api_key" == awon_live_* ]]

me_status="$(curl -sS -o /dev/null -w '%{http_code}' -H "X-API-Key: $api_key" "$open_base/me")"
invalid_status="$(curl -sS -o /dev/null -w '%{http_code}' -H 'X-API-Key: awon_live_invalid' "$open_base/me")"
columns_status="$(curl -sS -o "$tmp/columns.json" -w '%{http_code}' -H "X-API-Key: $api_key" \
  -H 'Content-Type: application/json' -d '{"columns":["총질소","T-N","공촌천_수온"]}' \
  "$open_base/mappings/columns")"
[[ "$(python3 -c 'import json,sys; print(json.load(sys.stdin)["count"])' < "$tmp/columns.json")" == 3 ]]

review_status="$(curl -sS -o /dev/null -w '%{http_code}' -H "X-API-Key: $api_key" \
  -H 'Content-Type: application/json' \
  -d '{"raw":"어원사내총질소","standard_code":"WQ-005","note":"배포 검증 후 삭제"}' "$open_base/reviews")"
curl -fsS -o "$tmp/override.json" -H "X-API-Key: $api_key" -H 'Content-Type: application/json' \
  -d '{"columns":["어원사내총질소"]}' "$open_base/mappings/columns"
override_source="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["items"][0]["source"])' < "$tmp/override.json")"

printf '측정일자,총질소\n2026-08-21,3.2\n' > "$tmp/sample.csv"
file_status="$(curl -sS -o "$tmp/file.json" -w '%{http_code}' -H "X-API-Key: $api_key" \
  -F "file=@$tmp/sample.csv" "$open_base/mappings/files")"
file_columns="$(python3 -c 'import json,sys; print(len(json.load(sys.stdin)["columns"]))' < "$tmp/file.json")"

set -a; source /etc/awon/awon.env; set +a
mysql -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e \
  "DELETE FROM organization_dictionary_terms WHERE organization_id=$org_id AND alias_raw='어원사내총질소';" >/dev/null
stored_raw="$(mysql -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e \
  "SELECT COUNT(id) FROM organization_api_keys WHERE key_hash='$api_key';")"
[[ "$stored_raw" == 0 ]]

echo "open_api_me=$me_status"
echo "invalid_key=$invalid_status"
echo "columns_mapping=$columns_status"
echo "organization_override=$review_status,source=$override_source"
echo "file_mapping=$file_status,columns=$file_columns"
echo "organization_id=$org_id"
echo "api_key=$api_key"
echo "INITIAL_OPEN_API_KEY_ISSUED"
