#!/usr/bin/env sh
set -eu

APP_DIR="${APP_DIR:-/volume1/docker/fjordlens}"
PHOTO_DIR="${PHOTO_DIR:-${APP_DIR}/Photos}"
DATA_DIR="${DATA_DIR:-${APP_DIR}/data}"

echo "==> Creating app directory: ${APP_DIR}"
mkdir -p "$APP_DIR"

echo "==> Creating default folders:"
echo "    Photos: ${PHOTO_DIR}"
echo "    Data:   ${DATA_DIR}"
mkdir -p "$PHOTO_DIR" "$DATA_DIR"

echo "==> Copy your project files into ${APP_DIR} or clone your GitHub repo there."
echo "Example:"
echo "  cd /volume1/docker"
echo "  git clone https://github.com/YOUR_USER/YOUR_REPO.git fjordlens"

echo "==> Make sure .env exists:"
echo "  cp .env.example .env"
echo "  vi .env"
echo ""
echo "Recommended defaults for .env on this NAS:"
echo "  PHOTO_DIR=${PHOTO_DIR}"
echo "  DATA_DIR=${DATA_DIR}"

echo "==> Start app:"
echo "  docker compose up -d --build"
