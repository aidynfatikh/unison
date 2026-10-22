#!/usr/bin/env bash
# One-time root setup: local name "unison" + nginx proxy on port 80.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
DIR="$(cd "$(dirname "$0")" && pwd)"

grep -qE '^\s*127\.0\.0\.1\s+.*\bunison\b' /etc/hosts || echo "127.0.0.1 unison unison.local" >> /etc/hosts
grep -qE '^\s*::1\s+.*\bunison\b' /etc/hosts || echo "::1 unison unison.local" >> /etc/hosts

cp "$DIR/deploy/nginx-unison.conf" /etc/nginx/sites-available/unison
ln -sf /etc/nginx/sites-available/unison /etc/nginx/sites-enabled/unison
nginx -t && systemctl reload nginx
echo "done -> open http://unison/"
