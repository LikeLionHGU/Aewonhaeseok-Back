#!/usr/bin/env bash
set -Eeuo pipefail
config=/etc/nginx/sites-available/awon-api
backup=/var/backups/awon/open-api-20260821/awon-api.nginx.before-open-api
cp "$config" "$backup"

if ! grep -q 'location /open-api/' "$config"; then
  awk '
    /    location \/swagger-ui\// && !inserted {
      print "    location /open-api/ {"
      print "        proxy_pass http://127.0.0.1:8080;"
      print "        proxy_set_header Host $host;"
      print "        proxy_set_header X-Real-IP $remote_addr;"
      print "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;"
      print "        proxy_set_header X-Forwarded-Proto $scheme;"
      print "        proxy_read_timeout 120s;"
      print "    }"
      print ""
      inserted=1
    }
    { print }
  ' "$config" > /tmp/awon-api.nginx.open-api
  install -o root -g root -m 0644 /tmp/awon-api.nginx.open-api "$config"
fi

nginx -t
systemctl reload nginx
status="$(curl -sS -o /dev/null -w '%{http_code}' https://1-201-116-24.sslip.io/open-api/v1/me)"
[[ "$status" == 401 ]]
echo "EXTERNAL_OPEN_API_WITHOUT_KEY=$status"
echo "OPEN_API_NGINX_ENABLED"
