#!/usr/bin/env sh
set -eu

APP_DIR="${APP_DIR:-/volume1/docker/fjordlens}"

echo "==> Updating FjordLens in ${APP_DIR}"
cd "$APP_DIR"

if [ -d .git ]; then
  echo "==> Pulling latest code from GitHub"
  git pull --ff-only
else
  echo "No .git folder found in ${APP_DIR}. Did you clone the repo?"
  exit 1
fi

echo "==> Rebuilding and restarting container"
docker compose up -d --build

echo "==> Done. Open: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo NAS-IP):${APP_PORT:-9080}"
