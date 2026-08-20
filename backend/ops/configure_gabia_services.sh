#!/usr/bin/env bash
set -Eeuo pipefail

install -d -o awon -g awon -m 0755 /opt/awon/app /opt/awon/repo
install -o awon -g awon -m 0644 /tmp/awon-backend.jar /opt/awon/app/awon-backend.jar
tar -xzf /tmp/awon-mapper-bundle.tar.gz -C /opt/awon/repo
chown -R awon:awon /opt/awon/repo

python3 -m venv /opt/awon/venv
/opt/awon/venv/bin/pip install --upgrade pip
/opt/awon/venv/bin/pip install \
  -r /opt/awon/repo/requirements.txt \
  -r /opt/awon/repo/backend/mapper_service/requirements.txt
chown -R awon:awon /opt/awon/venv

install -d -m 0750 /etc/awon
if [[ -s /etc/awon/awon.env ]]; then
  db_password="$(sed -n 's/^DB_PASSWORD=//p' /etc/awon/awon.env)"
else
  db_password="$(openssl rand -hex 24)"
fi

mysql -uroot -e "CREATE DATABASE IF NOT EXISTS awon CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -uroot -e "CREATE USER IF NOT EXISTS 'awon_app'@'localhost' IDENTIFIED BY '${db_password}';"
mysql -uroot -e "ALTER USER 'awon_app'@'localhost' IDENTIFIED BY '${db_password}';"
mysql -uroot -e "GRANT ALL PRIVILEGES ON awon.* TO 'awon_app'@'localhost'; FLUSH PRIVILEGES;"

cat > /etc/awon/awon.env <<EOF
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=awon
DB_USER=awon_app
DB_PASSWORD=${db_password}
MAPPER_BASE_URL=http://127.0.0.1:8000
MAPPER_TIMEOUT=30
STORAGE_ROOT=/srv/awon/uploads
SERVER_PORT=8080
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,http://1.201.116.24
EOF
chmod 0600 /etc/awon/awon.env
chown root:root /etc/awon/awon.env

cat > /etc/systemd/system/awon-mapper.service <<'EOF'
[Unit]
Description=Awon Python mapper service
After=network.target

[Service]
Type=simple
User=awon
Group=awon
WorkingDirectory=/opt/awon/repo/backend/mapper_service
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/awon/venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/awon-api.service <<'EOF'
[Unit]
Description=Awon Spring Boot API
After=network.target mysql.service awon-mapper.service
Requires=mysql.service
Wants=awon-mapper.service

[Service]
Type=simple
User=awon
Group=awon
EnvironmentFile=/etc/awon/awon.env
ExecStart=/usr/bin/java -Xms256m -Xmx1536m -jar /opt/awon/app/awon-backend.jar
Restart=always
RestartSec=5
SuccessExitStatus=143

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/nginx/sites-available/awon-api <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 100m;

    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location /open-api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location /swagger-ui/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /v3/api-docs {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /v3/api-docs/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        return 404;
    }
}
EOF

rm -f /etc/nginx/sites-enabled/default
ln -sfn /etc/nginx/sites-available/awon-api /etc/nginx/sites-enabled/awon-api
nginx -t
systemctl daemon-reload
systemctl enable awon-api awon-mapper
systemctl restart awon-mapper nginx

for _ in $(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then
    break
  fi
  sleep 1
done
curl --fail --silent http://127.0.0.1:8000/health
echo
echo 'SERVICES_CONFIGURED'
