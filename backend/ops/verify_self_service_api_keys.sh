#!/usr/bin/env bash
set -Eeuo pipefail

domain=1-201-116-24.sslip.io
base_url="https://${domain}"
credentials_file=/etc/awon/legacy-admin-credentials
cookie_jar="$(mktemp)"
login_body="$(mktemp)"
keys_body="$(mktemp)"
api_docs="$(mktemp)"
trap 'rm -f "$cookie_jar" "$login_body" "$keys_body" "$api_docs"' EXIT

source "$credentials_file"

login_status="$(curl --resolve "${domain}:443:127.0.0.1" -sS \
  -c "$cookie_jar" -o "$login_body" -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${email}\",\"password\":\"${password}\"}" \
  "${base_url}/api/v1/auth/login")"
[[ "$login_status" == "200" ]]

keys_status="$(curl --resolve "${domain}:443:127.0.0.1" -sS \
  -b "$cookie_jar" -o "$keys_body" -w '%{http_code}' \
  "${base_url}/api/v1/open-api/keys")"
[[ "$keys_status" == "200" ]]
grep -Eq '^\[.*\]$' "$keys_body"

curl -fsS http://127.0.0.1:8080/v3/api-docs -o "$api_docs"
python3 -c '
import json, sys
document = json.load(open(sys.argv[1], encoding="utf-8"))
operation = document["paths"]["/api/v1/open-api/keys"]["post"]
request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
schema_name = request_schema["$ref"].rsplit("/", 1)[-1]
rpm = document["components"]["schemas"][schema_name]["properties"]["requests_per_minute"]
assert rpm["maximum"] == 60, rpm
assert rpm["minimum"] == 1, rpm
assert rpm["default"] == 60, rpm
' "$api_docs"
systemctl is-active --quiet awon-api
systemctl is-active --quiet awon-mapper
systemctl is-active --quiet nginx
systemctl is-active --quiet mysql

echo "LOGIN=$login_status"
echo "AUTHENTICATED_KEYS=$keys_status"
echo "SWAGGER_SELF_SERVICE_PATH=present"
echo "SWAGGER_REQUESTS_PER_MINUTE=minimum:1,maximum:60,default:60"
echo "SERVICES=active"
