#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

echo "==> first_install_nas.sh now forwards to scripts/setup.sh"
sh "${SCRIPT_DIR}/setup.sh"
