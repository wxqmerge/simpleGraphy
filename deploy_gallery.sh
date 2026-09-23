#!/bin/bash
# deploy_gallery.sh
#
# Serve the simpleGraphy photo gallery over HTTPS on a chess4.us subdomain,
# using the same nginx + Let's Encrypt (certbot) approach as D:\hiker
# (see D:\hiker\deploy\update.sh steps 9-11 and D:\hiker\deploy\hiker.conf).
#
# The gallery is a static site (index.html + .thumbs/ + .lr/ + subdirs) and is
# NOT in git (galleries/ is gitignored), so transfer it to the server first:
#
#     # local machine, after generating the gallery:
#     python generate_gallery.py galleries/
#     scp -r galleries/ <user>@<server>:~/gallery-staging/
#
#     # then on the server:
#     SRC_DIR=~/gallery-staging ./deploy_gallery.sh
#
# Prerequisites on the server:
#   - nginx + certbot installed (sudo apt install nginx certbot rsync)
#   - DNS A/AAAA record for <SUBDOMAIN>.chess4.us -> this server's IP
#   - ports 80 and 443 open
#
# Usage:
#   ./deploy_gallery.sh                     deploy to gallery.chess4.us
#   SUBDOMAIN=photos ./deploy_gallery.sh    deploy to photos.chess4.us
#   ./deploy_gallery.sh --dry-run           show actions, change nothing
#   ./deploy_gallery.sh --help              help

set -euo pipefail

# ---- Configuration (override via env vars) ---------------------------------
SUBDOMAIN="${SUBDOMAIN:-gallery}"
DOMAIN="${DOMAIN:-chess4.us}"
FULL_DOMAIN="${SUBDOMAIN}.${DOMAIN}"
SRC_DIR="${SRC_DIR:-$(cd "$(dirname "$0")" && pwd)/galleries}"
WEB_ROOT="${WEB_ROOT:-/var/www/html/${SUBDOMAIN}}"
CERT_EMAIL="${CERT_EMAIL:-admin@${DOMAIN}}"
NGINX_CONF="/etc/nginx/sites-available/${SUBDOMAIN}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${SUBDOMAIN}"
CERTBOT_WELLKNOWN="/var/www/certbot"
DEPLOY_USER="$(whoami)"

# ---- Args -------------------------------------------------------------------
DRY_RUN=0
usage() {
  cat <<EOF
deploy_gallery.sh - serve the simpleGraphy gallery over HTTPS on ${DOMAIN}

Usage:
  ./deploy_gallery.sh                     deploy to ${SUBDOMAIN}.${DOMAIN}
  SUBDOMAIN=photos ./deploy_gallery.sh    deploy to photos.${DOMAIN}
  ./deploy_gallery.sh --dry-run           show what would happen, change nothing
  ./deploy_gallery.sh --help              this help

Env overrides: SUBDOMAIN, DOMAIN, SRC_DIR, WEB_ROOT, CERT_EMAIL
EOF
}
for arg in "$@"; do
  case "$arg" in
    --dry-run|--DRY_RUN) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $arg" >&2; usage; exit 1 ;;
  esac
done

# run a command, or just print it in dry-run mode
run()  { if [ "$DRY_RUN" = 1 ]; then echo "  [dry-run] $*"; else "$@"; fi; }
srun() { if [ "$DRY_RUN" = 1 ]; then echo "  [dry-run] sudo $*"; else sudo "$@"; fi; }

echo "=== Deploying gallery to https://${FULL_DOMAIN} ==="
echo "Source:   $SRC_DIR"
echo "Web root: $WEB_ROOT"
echo "Mode:     $([ "$DRY_RUN" = 1 ] && echo DRY-RUN || echo LIVE)"
echo ""

# 0. Sanity checks
if [ ! -d "$SRC_DIR" ]; then
  echo "ERROR: gallery source '$SRC_DIR' not found."
  echo "Transfer the gallery to the server first (see header), or set SRC_DIR."
  exit 1
fi
if [ ! -f "$SRC_DIR/index.html" ]; then
  echo "ERROR: '$SRC_DIR/index.html' not found."
  echo "Run 'python generate_gallery.py galleries/' first, or point SRC_DIR at the gallery."
  exit 1
fi

# 1. Copy gallery to web root
echo "[1/4] Copying gallery to $WEB_ROOT ..."
srun mkdir -p "$WEB_ROOT"
srun chown "${DEPLOY_USER}:www-data" "$WEB_ROOT"
if [ "$DRY_RUN" = 1 ]; then
  echo "  [dry-run] rsync -a --delete $SRC_DIR/ $WEB_ROOT/"
else
  if ! command -v rsync &>/dev/null; then
    echo "ERROR: rsync not installed. Install it: sudo apt install rsync"
    exit 1
  fi
  rsync -a --delete "$SRC_DIR/" "$WEB_ROOT/"
  find "$WEB_ROOT" -type d -exec chmod 755 {} +
  find "$WEB_ROOT" -type f -exec chmod 644 {} +
fi
echo "  Done."

# 2. Write nginx config
echo "[2/4] Writing nginx config to $NGINX_CONF ..."
if [ "$DRY_RUN" = 1 ]; then
  echo "  [dry-run] would write nginx config for $FULL_DOMAIN (HTTP->HTTPS + ACME + static root $WEB_ROOT)"
else
  CONF_TMP="$(mktemp)"
  cat > "$CONF_TMP" <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${FULL_DOMAIN};

    # Let's Encrypt certbot challenge
    location /.well-known/acme-challenge/ {
        root ${CERTBOT_WELLKNOWN};
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name ${FULL_DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${FULL_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${FULL_DOMAIN}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    root ${WEB_ROOT};
    index index.html;

    # Cache images (mirrors galleries/.htaccess)
    location ~* \.(jpg|jpeg|png|gif|webp|heic|heif|svg)\$ {
        expires 1 month;
        add_header Cache-Control "public";
    }

    location / {
        try_files \$uri \$uri/ =404;
    }
}
NGINX
  srun cp "$CONF_TMP" "$NGINX_CONF"
  rm -f "$CONF_TMP"
fi
echo "  Done."

# 3. Get/renew SSL certificate (certbot --standalone, same as hiker)
echo "[3/4] Getting SSL certificate for $FULL_DOMAIN ..."
if [ "$DRY_RUN" = 1 ]; then
  echo "  [dry-run] sudo certbot certonly --standalone -d $FULL_DOMAIN --non-interactive --agree-tos --email $CERT_EMAIL --key-type ecdsa"
else
  if ! command -v certbot &>/dev/null; then
    echo "ERROR: certbot not installed. Install it: sudo apt install certbot"
    exit 1
  fi
  # --standalone binds port 80 directly, so nginx must be stopped first (same as hiker).
  # If you'd rather not interrupt other sites, use --webroot -w $CERTBOT_WELLKNOWN instead.
  srun systemctl stop nginx
  if sudo certbot certonly --standalone -d "$FULL_DOMAIN" --non-interactive --agree-tos --email "$CERT_EMAIL" --key-type ecdsa; then
    echo "  SSL certificate obtained/renewed."
  else
    echo "  WARNING: certbot failed (cert may already exist). Continuing..."
  fi
fi

# 4. Enable site, test, restart nginx
echo "[4/4] Enabling site, testing and restarting nginx ..."
if [ "$DRY_RUN" = 1 ]; then
  echo "  [dry-run] sudo ln -sf $NGINX_CONF $NGINX_ENABLED"
  echo "  [dry-run] sudo nginx -t && sudo systemctl restart nginx"
else
  srun ln -sf "$NGINX_CONF" "$NGINX_ENABLED"
  if sudo nginx -t 2>&1 | grep -q "syntax is ok"; then
    srun systemctl restart nginx
    echo "  Nginx restarted."
  else
    echo "  ERROR: Nginx config test failed."
    exit 1
  fi
fi

echo ""
echo "=== Done. Gallery live at https://${FULL_DOMAIN} ==="
echo "Verify: curl -sI https://${FULL_DOMAIN} | head"
