#!/usr/bin/env bash
set -Eeuo pipefail

source /etc/awon/awon.env

systemctl stop awon-api awon-mapper

sha256sum /tmp/awon-old.sql.gz /tmp/awon-uploads.tar.gz /tmp/awon-ontology.tar.gz
gzip -t /tmp/awon-old.sql.gz
gzip -t /tmp/awon-uploads.tar.gz
gzip -t /tmp/awon-ontology.tar.gz

mysqldump -uroot --no-tablespaces --single-transaction awon \
  | gzip -9 > /var/backups/awon/new-server-before-data-restore.sql.gz
tar -C /data/awon -czf /var/backups/awon/uploads-before-data-restore.tar.gz uploads
tar -C /opt/awon/repo -czf /var/backups/awon/ontology-before-data-restore.tar.gz ontology

mysql -uroot -e "DROP DATABASE IF EXISTS awon;"
gzip -dc /tmp/awon-old.sql.gz | mysql -uroot
mysql -uroot -e "GRANT ALL PRIVILEGES ON awon.* TO 'awon_app'@'localhost'; FLUSH PRIVILEGES;"

find /data/awon/uploads -mindepth 1 -delete
tar -xzf /tmp/awon-uploads.tar.gz -C /data/awon
chown -R awon:awon /data/awon/uploads

rm -rf -- /opt/awon/repo/ontology
tar -xzf /tmp/awon-ontology.tar.gz -C /opt/awon/repo
chown -R awon:awon /opt/awon/repo/ontology

(
  cd /data/awon/uploads
  sha256sum -c /tmp/awon-uploads.sha256
)
(
  cd /opt/awon/repo/ontology
  sha256sum -c /tmp/awon-ontology.sha256
)

actual_counts=/tmp/awon-table-counts-actual.tsv
mysql -uroot -Nse \
  "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='awon' ORDER BY TABLE_NAME" \
  | while IFS= read -r table_name; do
      row_count="$(mysql -uroot -Nse "SELECT COUNT(*) FROM \`awon\`.\`${table_name}\`")"
      printf '%s\t%s\n' "${table_name}" "${row_count}"
    done > "${actual_counts}"
diff -u /tmp/awon-table-counts.tsv "${actual_counts}"

systemctl restart awon-mapper
systemctl start awon-api

for _ in $(seq 1 60); do
  if curl --fail --silent http://127.0.0.1:8080/api/v1/standards >/dev/null; then
    break
  fi
  sleep 1
done

curl --fail --silent http://127.0.0.1:8000/health
echo
curl --fail --silent http://127.0.0.1:8080/api/v1/standards
echo
systemctl is-active awon-api awon-mapper nginx mysql
echo 'RESTORE_OK'
