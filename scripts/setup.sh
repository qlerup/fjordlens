#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_DIR="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_DIR}/.env}"
EXAMPLE_ENV="${REPO_DIR}/.env.example"

echo "==> FjordLens setup"
echo "    Repo: ${REPO_DIR}"

if [ ! -f "$EXAMPLE_ENV" ]; then
  echo "ERROR: Missing .env.example in repo root."
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "==> Creating ${ENV_FILE} from .env.example"
  cp "$EXAMPLE_ENV" "$ENV_FILE"
else
  echo "==> Using existing env file: ${ENV_FILE}"
fi

echo "==> Running bootstrap (preflight + compose start)"
sh "${SCRIPT_DIR}/bootstrap.sh"
