#!/usr/bin/env bash
set -Eeuo pipefail

source /etc/awon/awon.env
export_dir=/tmp/awon-gabia-export

restart_old_on_error() {
  systemctl start awon-mapper awon-api || true
}
trap restart_old_on_error ERR

rm -rf -- "${export_dir}"
install -d -m 0700 "${export_dir}"

systemctl stop awon-api awon-mapper

client_file="${export_dir}/mysql-client.cnf"
cat > "${client_file}" <<EOF
[client]
host=${DB_HOST}
port=${DB_PORT}
user=${DB_USER}
password=${DB_PASSWORD}
EOF
chmod 0600 "${client_file}"

mysqldump --defaults-extra-file="${client_file}" \
  --single-transaction --routines --triggers --events --hex-blob \
  --no-tablespaces \
  --set-gtid-purged=OFF --databases "${DB_NAME}" \
  | gzip -9 > "${export_dir}/awon.sql.gz"

mysql --defaults-extra-file="${client_file}" -Nse \
  "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='${DB_NAME}' ORDER BY TABLE_NAME" \
  | while IFS= read -r table_name; do
      row_count="$(mysql --defaults-extra-file="${client_file}" -Nse \
        "SELECT COUNT(*) FROM \`${DB_NAME}\`.\`${table_name}\`")"
      printf '%s\t%s\n' "${table_name}" "${row_count}"
    done > "${export_dir}/table-counts.tsv"

tar -C /srv/awon -czf "${export_dir}/uploads.tar.gz" uploads
(
  cd /srv/awon/uploads
  find . -type f -print0 | sort -z | xargs -0 sha256sum
) > "${export_dir}/uploads.sha256"

tar -C /opt/awon/repo -czf "${export_dir}/ontology.tar.gz" ontology
(
  cd /opt/awon/repo/ontology
  find . -type f -print0 | sort -z | xargs -0 sha256sum
) > "${export_dir}/ontology.sha256"

rm -f -- "${client_file}"
sha256sum "${export_dir}/awon.sql.gz" \
  "${export_dir}/uploads.tar.gz" \
  "${export_dir}/ontology.tar.gz" > "${export_dir}/archives.sha256"
chown -R ubuntu:ubuntu "${export_dir}"

trap - ERR
echo 'EXPORT_OK'
cat "${export_dir}/table-counts.tsv"
cat "${export_dir}/archives.sha256"
