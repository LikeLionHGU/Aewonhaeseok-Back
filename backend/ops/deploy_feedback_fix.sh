#!/usr/bin/env bash
set -Eeuo pipefail

source /etc/awon/awon.env

mysql_args=(-u"${DB_USER}" -p"${DB_PASSWORD}" -h"${DB_HOST}" -P"${DB_PORT}" "${DB_NAME}")
test_paths=(
  /srv/awon/uploads/2026/08/17/b25ec0b3-3394-4029-9847-c71ff9e9d9d4.csv
  /srv/awon/uploads/2026/08/17/45ce6661-dc44-4f81-a4cf-b1a7185d7bfa.csv
  /srv/awon/uploads/2026/08/17/fe57b711-1bb3-4890-bf77-5a76a35ef437.csv
)

for path in "${test_paths[@]}"; do
  resolved="$(readlink -f -- "${path}")"
  if [[ "${resolved}" != /srv/awon/uploads/2026/08/17/* || ! -f "${resolved}" ]]; then
    echo "Refusing cleanup: unexpected test file path ${path}" >&2
    exit 1
  fi
done

matched_files="$(mysql "${mysql_args[@]}" -Nse "
  SELECT COUNT(*) FROM files
  WHERE (id=8 AND original_filename='audit.csv')
     OR (id=9 AND original_filename='cross.csv')
     OR (id=10 AND original_filename='low.csv');")"

if [[ "${matched_files}" != "3" ]]; then
  echo "Refusing cleanup: expected 3 exact database files, found ${matched_files}" >&2
  exit 1
fi

test -s /var/backups/awon/awon-before-feedback-cleanup-20260817.sql
mysql "${mysql_args[@]}" < /tmp/cleanup_frontend_audit.sql

install -d -m 0700 /var/backups/awon/feedback-test-files-20260817
for path in "${test_paths[@]}"; do
  mv -- "${path}" /var/backups/awon/feedback-test-files-20260817/
done

cp --preserve=mode,timestamps /opt/awon/app/awon-backend.jar \
  /var/backups/awon/awon-backend-before-feedback.jar
install -m 0644 /tmp/awon-backend-feedback.jar /opt/awon/app/awon-backend.jar
systemctl restart awon-api
systemctl is-active --quiet awon-api

mysql "${mysql_args[@]}" -Nse "
  SELECT CONCAT('files=', COUNT(*)) FROM files;
  SELECT CONCAT('analysis_runs=', COUNT(*)) FROM analysis_runs;
  SELECT CONCAT('pending_reviews=', COUNT(*)) FROM review_items WHERE verdict IS NULL;
  SELECT CONCAT('legacy_verdicts=', COUNT(*)) FROM review_items
    WHERE verdict IN ('approved','rejected','승인','기각');
  SELECT CONCAT('remaining_named_test_files=', COUNT(*)) FROM files
    WHERE original_filename IN ('audit.csv','cross.csv','low.csv');"
