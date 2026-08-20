#!/usr/bin/env bash
set -Eeuo pipefail

data_device=/dev/vdb
data_mount=/data

if [[ ! -b "${data_device}" ]]; then
  echo "Missing expected data disk: ${data_device}" >&2
  exit 1
fi

if [[ -z "$(lsblk -dn -o FSTYPE "${data_device}")" ]]; then
  mkfs.ext4 -F -L awon-data "${data_device}"
fi

install -d -m 0755 "${data_mount}"
data_uuid="$(blkid -s UUID -o value "${data_device}")"
if ! grep -q "UUID=${data_uuid}" /etc/fstab; then
  printf 'UUID=%s /data ext4 defaults,nofail 0 2\n' "${data_uuid}" >> /etc/fstab
fi
mountpoint -q "${data_mount}" || mount "${data_mount}"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  openjdk-21-jre-headless mysql-server nginx python3-venv python3-pip \
  rsync curl unzip ufw

if ! id awon >/dev/null 2>&1; then
  useradd --system --home-dir /opt/awon --shell /usr/sbin/nologin awon
fi

systemctl stop mysql
install -d -o mysql -g mysql -m 0750 /data/mysql
rsync -aHAX --numeric-ids /var/lib/mysql/ /data/mysql/

if ! mountpoint -q /var/lib/mysql; then
  if [[ ! -d /var/lib/mysql.root-initial ]]; then
    mv /var/lib/mysql /var/lib/mysql.root-initial
  fi
  install -d -o mysql -g mysql -m 0750 /var/lib/mysql
  mount --bind /data/mysql /var/lib/mysql
fi
if ! grep -q '^/data/mysql /var/lib/mysql ' /etc/fstab; then
  printf '/data/mysql /var/lib/mysql none bind 0 0\n' >> /etc/fstab
fi

install -d -o awon -g awon -m 0750 /data/awon/uploads
install -d -o root -g root -m 0700 /data/awon/backups
install -d -o awon -g awon -m 0750 /srv/awon/uploads
install -d -o root -g root -m 0700 /var/backups/awon

mountpoint -q /srv/awon/uploads || mount --bind /data/awon/uploads /srv/awon/uploads
mountpoint -q /var/backups/awon || mount --bind /data/awon/backups /var/backups/awon
if ! grep -q '^/data/awon/uploads /srv/awon/uploads ' /etc/fstab; then
  printf '/data/awon/uploads /srv/awon/uploads none bind 0 0\n' >> /etc/fstab
fi
if ! grep -q '^/data/awon/backups /var/backups/awon ' /etc/fstab; then
  printf '/data/awon/backups /var/backups/awon none bind 0 0\n' >> /etc/fstab
fi

systemctl enable --now mysql nginx

if ! swapon --show=NAME --noheadings | grep -q '^/swapfile$'; then
  if [[ ! -f /swapfile ]]; then
    fallocate -l 2G /swapfile
    chmod 0600 /swapfile
    mkswap /swapfile
  fi
  swapon /swapfile
fi
if ! grep -q '^/swapfile ' /etc/fstab; then
  printf '/swapfile none swap sw 0 0\n' >> /etc/fstab
fi

ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo 'BOOTSTRAP_OK'
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS
free -h
systemctl is-active mysql nginx
