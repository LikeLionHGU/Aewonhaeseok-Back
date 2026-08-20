#!/usr/bin/env bash
set -euo pipefail

set -a
source /etc/awon/awon.env
set +a

mysql -h "$DB_HOST" -P "$DB_PORT" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -Nse "
SELECT 'EXACT_HANGANG_COD';
SELECT u.email,
       f.id,
       f.original_filename,
       COUNT(*) AS cod_rows,
       MIN(m.measured_on) AS first_date,
       MAX(m.measured_on) AS last_date,
       MIN(m.value_num) AS min_value,
       MAX(m.value_num) AS max_value
  FROM measurements m
  JOIN files f ON f.id = m.file_id
  JOIN app_users u ON u.id = f.owner_user_id
 WHERE m.site_name = '한강'
   AND m.item_code = 'WQ-003'
 GROUP BY u.email, f.id, f.original_filename
 ORDER BY f.id;

SELECT 'ALL_COD_BY_SITE_AND_FILE';
SELECT u.email,
       f.id,
       f.original_filename,
       COALESCE(m.site_name, '(NULL)') AS site_name,
       COUNT(*) AS cod_rows,
       MIN(m.measured_on) AS first_date,
       MAX(m.measured_on) AS last_date
  FROM measurements m
  JOIN files f ON f.id = m.file_id
  JOIN app_users u ON u.id = f.owner_user_id
 WHERE m.item_code = 'WQ-003'
 GROUP BY u.email, f.id, f.original_filename, m.site_name
 ORDER BY cod_rows DESC, f.id
 LIMIT 100;

SELECT 'FILES_NAMED_HANGANG';
SELECT u.email, f.id, f.original_filename
  FROM files f
  JOIN app_users u ON u.id = f.owner_user_id
 WHERE f.original_filename LIKE '%한강%'
 ORDER BY f.id;

SELECT 'RECENT_QUARTER_COD_ANALYSES';
SELECT u.email,
       ar.execution_id,
       ar.conditions,
       ar.exceeded_count,
       ar.ran_at
  FROM analysis_runs ar
  JOIN app_users u ON u.id = ar.owner_user_id
 WHERE ar.conditions LIKE '%WQ-003%'
   AND ar.conditions LIKE '%quarter%'
 ORDER BY ar.ran_at DESC
 LIMIT 20;
"
