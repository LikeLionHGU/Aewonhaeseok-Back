#!/usr/bin/env bash
set -Eeuo pipefail

set -a
source /etc/awon/awon.env
set +a

mysql -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -Nse "
SET @user_id := (SELECT id FROM app_users WHERE email='legacy-admin@aewonhaeseo.local');
SELECT CONCAT('user_id=', COALESCE(@user_id, 'missing'));
SELECT CONCAT('files=', COUNT(*)) FROM files WHERE owner_user_id=@user_id;
SELECT CONCAT('mapping_runs=', COUNT(*)) FROM mapping_runs mr JOIN files f ON f.id=mr.file_id WHERE f.owner_user_id=@user_id;
SELECT CONCAT('mapping_columns=', COUNT(*)) FROM mapping_columns mc JOIN mapping_runs mr ON mr.id=mc.mapping_run_id JOIN files f ON f.id=mr.file_id WHERE f.owner_user_id=@user_id;
SELECT CONCAT('review_items=', COUNT(*)) FROM review_items ri JOIN files f ON f.id=ri.file_id WHERE f.owner_user_id=@user_id;
SELECT CONCAT('measurements=', COUNT(*)) FROM measurements m JOIN files f ON f.id=m.file_id WHERE f.owner_user_id=@user_id;
SELECT CONCAT('ingestion_runs=', COUNT(*)) FROM ingestion_runs ir JOIN files f ON f.id=ir.file_id WHERE f.owner_user_id=@user_id;
SELECT CONCAT('analysis_runs=', COUNT(*)) FROM analysis_runs WHERE owner_user_id=@user_id;
SELECT CONCAT('stored_bytes=', COALESCE(SUM(size_bytes),0)) FROM files WHERE owner_user_id=@user_id;
SELECT CONCAT('stored_path=', stored_path) FROM files WHERE owner_user_id=@user_id ORDER BY id;
"
