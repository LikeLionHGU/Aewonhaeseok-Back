#!/usr/bin/env bash
set -Eeuo pipefail

domain=1-201-116-24.sslip.io
base_url="https://${domain}"
backup_dir=/var/backups/awon/admin-data-purge-20260821-034814
cookie_jar="$(mktemp)"
login_body="$(mktemp)"
files_body="$(mktemp)"
reviews_body="$(mktemp)"
analyses_body="$(mktemp)"
trap 'rm -f "$cookie_jar" "$login_body" "$files_body" "$reviews_body" "$analyses_body"' EXIT

set -a
source /etc/awon/awon.env
source /etc/awon/legacy-admin-credentials
set +a

login_status="$(curl --resolve "${domain}:443:127.0.0.1" -sS \
  -c "$cookie_jar" -o "$login_body" -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${email}\",\"password\":\"${password}\"}" \
  "${base_url}/api/v1/auth/login")"
[[ "$login_status" == "200" ]]

for resource in files reviews analyses; do
  output_variable="${resource}_body"
  output_file="${!output_variable}"
  status="$(curl --resolve "${domain}:443:127.0.0.1" -sS \
    -b "$cookie_jar" -o "$output_file" -w '%{http_code}' \
    "${base_url}/api/v1/${resource}")"
  [[ "$status" == "200" ]]
done

python3 -c '
import json, sys
for path in sys.argv[1:]:
    page = json.load(open(path, encoding="utf-8"))
    assert page["total"] == 0, (path, page["total"])
    assert page["items"] == [], (path, page["items"])
' "$files_body" "$reviews_body" "$analyses_body"

backup_files="$(find "$backup_dir/files" -maxdepth 1 -type f | wc -l)"
[[ "$backup_files" == "39" ]]

remaining_originals=0
while IFS= read -r backup_file; do
  filename="$(basename "$backup_file")"
  if find "$STORAGE_ROOT" -type f -name "$filename" -print -quit | grep -q .; then
    remaining_originals=$((remaining_originals + 1))
  fi
done < <(find "$backup_dir/files" -maxdepth 1 -type f)
[[ "$remaining_originals" == "0" ]]

systemctl is-active --quiet awon-api
echo "LOGIN=$login_status"
echo "FILES_API_TOTAL=0"
echo "REVIEWS_API_TOTAL=0"
echo "ANALYSES_API_TOTAL=0"
echo "BACKUP_FILES=$backup_files"
echo "ORIGINAL_FILES_REMAINING=$remaining_originals"
echo "ADMIN_DATA_EMPTY_VERIFIED"
