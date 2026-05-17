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
# APP_USER defaults to whoever invoked sudo. If you ran as actual root
# (no sudo), set APP_USER explicitly in deploy.env.
APP_USER="${APP_USER:-${SUDO_USER:-}}"
APP_DIR="${APP_DIR:-/opt/aporeka/app}"
if [[ -z "$APP_USER" ]]; then
    echo "Cannot determine APP_USER (no SUDO_USER and not set in deploy.env)." >&2
    echo "Set APP_USER in deploy.env to the OS user that should own the checkout." >&2
    exit 1
fi
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
mkdir -p "$APP_DIR" /var/www/aporeka
chown -R "$APP_USER:$APP_USER" "$(dirname "$APP_DIR")" /var/www/aporeka

if [[ ! -d "$APP_DIR/.git" ]]; then
    echo
    echo "Repo not found at $APP_DIR. Clone it (or rsync from your dev machine), then re-run bootstrap." >&2
    echo "  Example: sudo -u $APP_USER git clone <repo-url> $APP_DIR" >&2
    exit 1
fi

echo "==> Rendering nginx site config"
envsubst '${APP_HOSTNAME}' \
    < "$SCRIPT_DIR/nginx.conf.template" \
    > /etc/nginx/sites-available/aporeka
ln -sf /etc/nginx/sites-available/aporeka /etc/nginx/sites-enabled/aporeka
rm -f /etc/nginx/sites-enabled/default
nginx -t

echo "==> Rendering systemd unit"
envsubst '${APP_USER} ${APP_DIR}' \
    < "$SCRIPT_DIR/aporeka.service" \
    > /etc/systemd/system/aporeka.service
systemctl daemon-reload

echo "==> Rendering /etc/aporeka.env"
if [[ -f /etc/aporeka.env ]]; then
    echo "    /etc/aporeka.env already exists; not overwriting."
else
    envsubst '${APP_HOSTNAME} ${APP_DIR}' \
        < "$SCRIPT_DIR/aporeka.env.template" \
        > /etc/aporeka.env
    chmod 600 /etc/aporeka.env
    chown root:root /etc/aporeka.env
fi

echo "==> Installing sudoers entry for deploy.sh"
cat > /etc/sudoers.d/aporeka <<EOF
$APP_USER ALL=(root) NOPASSWD: /usr/bin/systemctl restart aporeka, /usr/bin/systemctl reload nginx, /usr/sbin/nginx -t, /usr/bin/systemctl status aporeka
EOF
chmod 440 /etc/sudoers.d/aporeka
visudo -c -f /etc/sudoers.d/aporeka

echo "==> Reloading nginx"
systemctl reload nginx || systemctl start nginx

cat <<EOF

Bootstrap complete.

Next steps:
  1. Edit /etc/aporeka.env and replace 'replace-me' with the real
     OPENROUTER_API_KEY. (sudo nano /etc/aporeka.env)
  2. As $APP_USER, run the first deploy:
       sudo -u $APP_USER bash $SCRIPT_DIR/deploy.sh
  3. Once the app responds on http://$APP_HOSTNAME, enable HTTPS:
       sudo certbot --nginx -d $APP_HOSTNAME --non-interactive --agree-tos -m $ADMIN_EMAIL
  4. Enable boot persistence:
       sudo systemctl enable aporeka

EOF
