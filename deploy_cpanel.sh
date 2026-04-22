#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$SCRIPT_DIR}"
LIVE_DIR="${LIVE_DIR:-/mnt/jupiter/waonline/public_html/zender-webhook}"
BRANCH="${BRANCH:-main}"
SKIP_PULL="${SKIP_PULL:-0}"

echo "==> Repo: $REPO_DIR"
echo "==> Destino: $LIVE_DIR"

if [ ! -d "$REPO_DIR" ]; then
  echo "ERROR: no existe el directorio del repo: $REPO_DIR" >&2
  exit 1
fi

if [ ! -d "$LIVE_DIR" ]; then
  echo "ERROR: no existe el directorio de destino: $LIVE_DIR" >&2
  exit 1
fi

mkdir -p "$LIVE_DIR/tmp"

if [ "$SKIP_PULL" != "1" ]; then
  echo "==> Haciendo git pull en la rama $BRANCH"
  git -C "$REPO_DIR" pull origin "$BRANCH"
else
  echo "==> SKIP_PULL=1, omitiendo git pull"
fi

echo "==> Copiando codigo sin tocar .env ni archivos runtime"
(
  cd "$REPO_DIR"
  tar \
    --exclude='.git' \
    --exclude='.env' \
    --exclude='tmp' \
    --exclude='venv' \
    --exclude='virtualenv' \
    --exclude='__pycache__' \
    --exclude='nohup.out' \
    --exclude='stderr.log' \
    --exclude='webhook_debug.log' \
    --exclude='webhook_debug.log.1' \
    -cf - .
) | tar --no-same-owner --no-same-permissions -xf - -C "$LIVE_DIR"

echo "==> Corrigiendo permisos seguros para Apache/Passenger"
find "$LIVE_DIR" -type d -exec chmod 755 {} \;
find "$LIVE_DIR" -type f ! -name '.env' -exec chmod 644 {} \;

if [ -f "$LIVE_DIR/.env" ]; then
  chmod 600 "$LIVE_DIR/.env"
fi

touch "$LIVE_DIR/tmp/restart.txt"

echo "==> Despliegue terminado"
echo "==> Prueba en navegador: https://wa.onlinecomprafacil.com/zender-webhook/"
