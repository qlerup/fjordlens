#!/usr/bin/env sh
set -eu

APP_DIR="${APP_DIR:-/volume1/docker/fjordlens}"

echo "==> Creating app directory: ${APP_DIR}"
mkdir -p "$APP_DIR"

echo "==> Copy your project files into ${APP_DIR} or clone your GitHub repo there."
echo "Example:"
echo "  cd /volume1/docker"
echo "  git clone https://github.com/YOUR_USER/YOUR_REPO.git fjordlens"

echo "==> Make sure .env exists:"
echo "  cp .env.example .env"
echo "  vi .env"

echo "==> Start app:"
echo "  docker compose up -d --build"
