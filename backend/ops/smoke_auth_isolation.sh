#!/usr/bin/env bash
set -Eeuo pipefail

base=http://127.0.0.1:8080/api/v1
suffix="$(date +%s)"
email1="auth-smoke-${suffix}-one@example.com"
email2="auth-smoke-${suffix}-two@example.com"
password='Smoke-test-password-2026!'

set -a
source /etc/awon/awon.env
set +a

db() { mysql -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" "$@"; }
cleanup() {
  db -e "DELETE ar FROM analysis_runs ar JOIN app_users u ON u.id=ar.owner_user_id WHERE u.email IN ('$email1','$email2');
         DELETE FROM app_users WHERE email IN ('$email1','$email2');" >/dev/null 2>&1 || true
  rm -f /tmp/auth-smoke-headers-1 /tmp/auth-smoke-headers-2 /tmp/auth-smoke-body
}
trap cleanup EXIT

json_value() {
  python3 -c "import json,sys; print(json.load(sys.stdin)$1)"
}

anonymous_total="$(curl -fsS "$base/files?page=1&size=1" | json_value "['total']")"
[[ "$anonymous_total" -gt 0 ]]

curl -fsS -D /tmp/auth-smoke-headers-1 -o /tmp/auth-smoke-body \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$email1\",\"password\":\"$password\",\"display_name\":\"격리테스트1\"}" \
  "$base/auth/register"
token1="$(sed -n 's/^[Ss]et-[Cc]ookie: AWON_ACCESS_TOKEN=\([^;]*\).*/\1/p' /tmp/auth-smoke-headers-1 | tr -d '\r')"
[[ -n "$token1" ]]

curl -fsS -D /tmp/auth-smoke-headers-2 -o /dev/null \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$email2\",\"password\":\"$password\",\"display_name\":\"격리테스트2\"}" \
  "$base/auth/register"
token2="$(sed -n 's/^[Ss]et-[Cc]ookie: AWON_ACCESS_TOKEN=\([^;]*\).*/\1/p' /tmp/auth-smoke-headers-2 | tr -d '\r')"
[[ -n "$token2" ]]

me_email="$(curl -fsS -H "Cookie: AWON_ACCESS_TOKEN=$token1" "$base/auth/me" | json_value "['email']")"
[[ "$me_email" == "$email1" ]]

user_total="$(curl -fsS -H "Cookie: AWON_ACCESS_TOKEN=$token1" "$base/files?page=1&size=1" | json_value "['total']")"
[[ "$user_total" == 0 ]]

legacy_file_id="$(db -e 'SELECT id FROM files WHERE owner_user_id=1 ORDER BY id LIMIT 1;')"
foreign_status="$(curl -sS -o /dev/null -w '%{http_code}' \
  -H "Cookie: AWON_ACCESS_TOKEN=$token1" "$base/files/$legacy_file_id")"
[[ "$foreign_status" == 404 ]]

curl -fsS -H 'Content-Type: application/json' \
  -H "Cookie: AWON_ACCESS_TOKEN=$token1" -d '{}' "$base/analyses" > /tmp/auth-smoke-body
execution_id="$(json_value "['execution_id']" < /tmp/auth-smoke-body)"
other_analysis_status="$(curl -sS -o /dev/null -w '%{http_code}' \
  -H "Cookie: AWON_ACCESS_TOKEN=$token2" "$base/analyses/$execution_id")"
[[ "$other_analysis_status" == 404 ]]

review_total="$(curl -fsS -H "Cookie: AWON_ACCESS_TOKEN=$token1" \
  "$base/reviews?page=1&size=1" | json_value "['total']")"
[[ "$review_total" == 0 ]]

curl -fsS http://127.0.0.1:8080/v3/api-docs | grep -q 'cookieAuth'
echo "anonymous_legacy_files=$anonymous_total"
echo "authenticated_user_files=$user_total"
echo "foreign_file_status=$foreign_status"
echo "foreign_analysis_status=$other_analysis_status"
echo "AUTH_ISOLATION_SMOKE_OK"
