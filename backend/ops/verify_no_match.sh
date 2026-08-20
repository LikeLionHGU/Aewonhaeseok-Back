#!/usr/bin/env bash
set -Eeuo pipefail

source /etc/awon/awon.env
mysql_args=(-u"${DB_USER}" -p"${DB_PASSWORD}" -h"${DB_HOST}" -P"${DB_PORT}" "${DB_NAME}")

reset_smoke_data() {
  mysql "${mysql_args[@]}" -e "
    UPDATE review_items
    SET verdict=NULL, verdict_note=NULL, reviewed_by=NULL, reviewed_at=NULL
    WHERE id=4 AND file_id=1 AND reviewed_by='deployment-smoke';
    UPDATE files SET status='reviewing' WHERE id=1;" >/dev/null
}
trap reset_smoke_data EXIT

pending="$(mysql "${mysql_args[@]}" -Nse "
  SELECT COUNT(*) FROM review_items
  WHERE id=4 AND file_id=1 AND verdict IS NULL;")"
if [[ "${pending}" != "1" ]]; then
  echo "Refusing smoke test: review 4 is no longer pending" >&2
  exit 1
fi

response="$(curl --fail --silent --show-error \
  -H 'Content-Type: application/json' \
  -d '{"verdict":"no_match","reviewed_by":"deployment-smoke"}' \
  "http://127.0.0.1:${SERVER_PORT}/api/v1/reviews/4/verdict")"

stored="$(mysql "${mysql_args[@]}" -Nse "SELECT verdict FROM review_items WHERE id=4;")"
if [[ "${stored}" != "no_match" || "${response}" != *'"verdict":"no_match"'* ]]; then
  echo "no_match verification failed: stored=${stored} response=${response}" >&2
  exit 1
fi

echo "no_match_api=passed"
