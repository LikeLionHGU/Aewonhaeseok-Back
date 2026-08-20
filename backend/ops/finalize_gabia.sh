#!/usr/bin/env bash
set -Eeuo pipefail

backup_dir=/var/backups/awon/gabia-migration-20260818
install -d -o root -g root -m 0700 "${backup_dir}"
install -o root -g root -m 0600 /tmp/awon-old.sql.gz "${backup_dir}/awon-final.sql.gz"
install -o root -g root -m 0600 /tmp/awon-uploads.tar.gz "${backup_dir}/uploads-final.tar.gz"
install -o root -g root -m 0600 /tmp/awon-ontology.tar.gz "${backup_dir}/ontology-final.tar.gz"
install -o root -g root -m 0600 /tmp/awon-table-counts.tsv "${backup_dir}/table-counts.tsv"
install -o root -g root -m 0600 /tmp/awon-uploads.sha256 "${backup_dir}/uploads.sha256"
install -o root -g root -m 0600 /tmp/awon-ontology.sha256 "${backup_dir}/ontology.sha256"

if ! grep -q '^SERVER_ADDRESS=' /etc/awon/awon.env; then
  printf 'SERVER_ADDRESS=127.0.0.1\n' >> /etc/awon/awon.env
fi

cat > /etc/ssh/sshd_config.d/99-awon-hardening.conf <<'EOF'
PasswordAuthentication no
PermitRootLogin no
EOF
sshd -t
systemctl reload ssh
systemctl restart awon-api

for _ in $(seq 1 60); do
  if curl --fail --silent http://127.0.0.1:8080/api/v1/standards >/dev/null; then
    break
  fi
  sleep 1
done
curl --fail --silent http://127.0.0.1:8080/api/v1/standards >/dev/null

rm -f -- \
  /tmp/awon-old.sql.gz \
  /tmp/awon-uploads.tar.gz \
  /tmp/awon-ontology.tar.gz \
  /tmp/awon-table-counts.tsv \
  /tmp/awon-uploads.sha256 \
  /tmp/awon-ontology.sha256 \
  /tmp/awon-table-counts-actual.tsv \
  /tmp/awon-backend.jar \
  /tmp/awon-mapper-bundle.tar.gz \
  /tmp/bootstrap_gabia.sh \
  /tmp/configure_gabia_services.sh \
  /tmp/restore_gabia_data.sh \
  /tmp/finalize_gabia.sh

echo 'FINALIZE_OK'
systemctl is-active awon-api awon-mapper nginx mysql
ss -lntp | grep -E ':(80|3306|8000|8080) '
