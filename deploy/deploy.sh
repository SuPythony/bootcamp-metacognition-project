#!/usr/bin/env bash
# Idempotent redeploy. Run as $APP_USER on the box:
#   bash deploy/deploy.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ ! -f "$SCRIPT_DIR/deploy.env" ]]; then
    echo "Missing $SCRIPT_DIR/deploy.env (copy from deploy.env.example and edit)." >&2
    exit 1
fi

set -a
# shellcheck disable=SC1091
source "$SCRIPT_DIR/deploy.env"
set +a

: "${APP_HOSTNAME:?must be set in deploy.env}"
APP_USER="${APP_USER:-$(whoami)}"
APP_DIR="${APP_DIR:-/opt/socratic-tutor/app}"

if [[ "$(whoami)" != "$APP_USER" ]]; then
    echo "deploy.sh should be run as '$APP_USER' (current: $(whoami))." >&2
    echo "Either run as $APP_USER, or update APP_USER in deploy.env." >&2
    exit 1
fi

echo "==> Pulling latest"
cd "$APP_DIR"
git pull --ff-only

echo "==> Installing backend dependencies"
cd "$APP_DIR/backend"
if [[ ! -d venv ]]; then
    python3 -m venv venv
fi
venv/bin/pip install --upgrade pip
venv/bin/pip install -e ".[dev,math]"

echo "==> Building frontend"
cd "$APP_DIR/frontend"
# Unset any inherited Vite vars so .env.production wins predictably.
unset VITE_API_URL VITE_USE_MOCK
npm ci
npm run build

echo "==> Publishing static bundle"
rsync -a --delete "$APP_DIR/frontend/dist/" /var/www/socratic-tutor/

echo "==> Restarting backend"
echo "    (in-flight sessions will be reset — sessions are in-memory by design)"
sudo /usr/bin/systemctl restart socratic-tutor

echo "==> Reloading nginx"
sudo /usr/sbin/nginx -t
sudo /usr/bin/systemctl reload nginx

echo "==> Smoke test"
for i in 1 2 3 4 5; do
    if curl -sf http://127.0.0.1:8000/health >/dev/null; then
        echo "    backend is up"
        break
    fi
    if [[ $i -eq 5 ]]; then
        echo "    backend did not respond after 5 tries; check: sudo journalctl -u socratic-tutor -n 50" >&2
        exit 1
    fi
    sleep 2
done

curl -sf http://127.0.0.1:8000/specializations >/dev/null && echo "    /specializations OK"

echo
echo "Deployed at https://$APP_HOSTNAME"
