#!/usr/bin/env bash
set -Eeuo pipefail

base=https://1-201-116-24.sslip.io/api/v1
credentials=/etc/awon/legacy-admin-credentials
headers=/tmp/awon-https-auth-headers
body=/tmp/awon-https-auth-body
trap 'rm -f "$headers" "$body"' EXIT

email="$(sed -n 's/^email=//p' "$credentials")"
password="$(sed -n 's/^password=//p' "$credentials")"
payload="$(python3 -c 'import json,sys; print(json.dumps({"email":sys.argv[1],"password":sys.argv[2]}))' \
  "$email" "$password")"

login_status="$(curl -sS -D "$headers" -o "$body" -w '%{http_code}' \
  -H 'Content-Type: application/json' -d "$payload" "$base/auth/login")"
[[ "$login_status" == 200 ]]
grep -qi 'Set-Cookie: AWON_ACCESS_TOKEN=' "$headers"
grep -qi 'HttpOnly' "$headers"
grep -qi 'Secure' "$headers"
grep -qi 'SameSite=Strict' "$headers"

token="$(sed -n 's/^[Ss]et-[Cc]ookie: AWON_ACCESS_TOKEN=\([^;]*\).*/\1/p' "$headers" | tr -d '\r')"
[[ -n "$token" ]]

me_status="$(curl -sS -o /dev/null -w '%{http_code}' \
  -H "Cookie: AWON_ACCESS_TOKEN=$token" "$base/auth/me")"
files_status="$(curl -sS -o "$body" -w '%{http_code}' \
  -H "Cookie: AWON_ACCESS_TOKEN=$token" "$base/files?size=1")"
file_total="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["total"])' < "$body")"

unauth_files="$(curl -sS -o /dev/null -w '%{http_code}' "$base/files?size=1")"
unauth_analyses="$(curl -sS -o /dev/null -w '%{http_code}' "$base/analyses?size=1")"
unauth_measurements="$(curl -sS -o /dev/null -w '%{http_code}' "$base/measurements/summary")"

[[ "$me_status" == 200 ]]
[[ "$files_status" == 200 ]]
[[ "$file_total" -gt 0 ]]
[[ "$unauth_files" == 401 ]]
[[ "$unauth_analyses" == 401 ]]
[[ "$unauth_measurements" == 401 ]]

echo "https_login=$login_status"
echo "https_me=$me_status"
echo "authenticated_files=$files_status,total=$file_total"
echo "unauthenticated_files=$unauth_files"
echo "unauthenticated_analyses=$unauth_analyses"
echo "unauthenticated_measurements=$unauth_measurements"
echo "HTTPS_AUTH_VERIFIED"
