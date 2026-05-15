#!/usr/bin/env bash
# One-time first-deploy setup. Idempotent — safe to re-run.
# Run as root: sudo bash deploy/bootstrap.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ $EUID -ne 0 ]]; then
    echo "bootstrap.sh must be run as root (use sudo)." >&2
    exit 1
fi

if [[ ! -f "$SCRIPT_DIR/deploy.env" ]]; then
    echo "Create $SCRIPT_DIR/deploy.env from deploy.env.example first." >&2
    exit 1
fi

set -a
# shellcheck disable=SC1091
source "$SCRIPT_DIR/deploy.env"
set +a

: "${APP_HOSTNAME:?must be set in deploy.env}"
: "${ADMIN_EMAIL:?must be set in deploy.env}"
APP_USER="${APP_USER:-ubuntu}"
APP_DIR="${APP_DIR:-/opt/socratic-tutor/app}"
export APP_HOSTNAME ADMIN_EMAIL APP_USER APP_DIR

if ! command -v apt >/dev/null 2>&1; then
    echo "This script assumes Debian/Ubuntu (apt). Adapt manually for other distros." >&2
    exit 1
fi

if ! id "$APP_USER" >/dev/null 2>&1; then
    echo "User '$APP_USER' does not exist. Set APP_USER in deploy.env to an existing user." >&2
    exit 1
fi

echo "==> Installing system packages"
apt update
apt install -y \
    python3-venv python3-pip \
    nginx \
    certbot python3-certbot-nginx \
    git rsync curl ca-certificates gnupg \
    gettext-base

if ! command -v node >/dev/null 2>&1 || ! node --version | grep -qE '^v(2[0-9]|[3-9][0-9])\.'; then
    echo "==> Installing Node 20 via NodeSource"
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt install -y nodejs
else
    echo "==> Node already installed ($(node --version)); skipping NodeSource setup"
fi

echo "==> Creating directories"
mkdir -p "$APP_DIR" /var/www/socratic-tutor
chown -R "$APP_USER:$APP_USER" "$(dirname "$APP_DIR")" /var/www/socratic-tutor

if [[ ! -d "$APP_DIR/.git" ]]; then
    echo
    echo "Repo not found at $APP_DIR. Clone it (or rsync from your dev machine), then re-run bootstrap." >&2
    echo "  Example: sudo -u $APP_USER git clone <repo-url> $APP_DIR" >&2
    exit 1
fi

echo "==> Rendering nginx site config"
envsubst '${APP_HOSTNAME}' \
    < "$SCRIPT_DIR/nginx.conf.template" \
    > /etc/nginx/sites-available/socratic-tutor
ln -sf /etc/nginx/sites-available/socratic-tutor /etc/nginx/sites-enabled/socratic-tutor
rm -f /etc/nginx/sites-enabled/default
nginx -t

echo "==> Rendering systemd unit"
envsubst '${APP_USER} ${APP_DIR}' \
    < "$SCRIPT_DIR/socratic-tutor.service" \
    > /etc/systemd/system/socratic-tutor.service
systemctl daemon-reload

echo "==> Rendering /etc/socratic-tutor.env"
if [[ -f /etc/socratic-tutor.env ]]; then
    echo "    /etc/socratic-tutor.env already exists; not overwriting."
else
    envsubst '${APP_HOSTNAME} ${APP_DIR}' \
        < "$SCRIPT_DIR/socratic-tutor.env.template" \
        > /etc/socratic-tutor.env
    chmod 600 /etc/socratic-tutor.env
    chown root:root /etc/socratic-tutor.env
fi

echo "==> Installing sudoers entry for deploy.sh"
cat > /etc/sudoers.d/socratic-tutor <<EOF
$APP_USER ALL=(root) NOPASSWD: /usr/bin/systemctl restart socratic-tutor, /usr/bin/systemctl reload nginx, /usr/sbin/nginx -t, /usr/bin/systemctl status socratic-tutor
EOF
chmod 440 /etc/sudoers.d/socratic-tutor
visudo -c -f /etc/sudoers.d/socratic-tutor

echo "==> Reloading nginx"
systemctl reload nginx || systemctl start nginx

cat <<EOF

Bootstrap complete.

Next steps:
  1. Edit /etc/socratic-tutor.env and replace 'replace-me' with the real
     OPENROUTER_API_KEY. (sudo nano /etc/socratic-tutor.env)
  2. As $APP_USER, run the first deploy:
       sudo -u $APP_USER bash $SCRIPT_DIR/deploy.sh
  3. Once the app responds on http://$APP_HOSTNAME, enable HTTPS:
       sudo certbot --nginx -d $APP_HOSTNAME --non-interactive --agree-tos -m $ADMIN_EMAIL
  4. Enable boot persistence:
       sudo systemctl enable socratic-tutor

EOF
