#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_DIR="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_DIR}/.env}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker command not found."
  exit 1
fi
if ! command -v findmnt >/dev/null 2>&1; then
  echo "ERROR: findmnt command not found (install util-linux)."
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose plugin not available."
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: Missing env file: $ENV_FILE"
  echo "Create it first, for example:"
  echo "  cp ${REPO_DIR}/.env.example ${REPO_DIR}/.env"
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

: "${DATA_DIR:=/volume1/docker/fjordlens/data}"
: "${UPLOADS_HOST_DIR:=/volume1/docker/fjordlens/data/uploads}"
: "${THUMBS_HOST_DIR:=/volume1/docker/fjordlens/data/thumbs}"
: "${ENABLE_LIBRARY_SOURCE:=0}"

# Optional strict filesystem checks used by this script only.
# Example for NFS:
#   EXPECT_UPLOADS_FSTYPES=nfs,nfs4
#   EXPECT_THUMBS_FSTYPES=nfs,nfs4
#   EXPECT_PHOTO_FSTYPES=nfs,nfs4
: "${EXPECT_DATA_FSTYPES:=}"
: "${EXPECT_UPLOADS_FSTYPES:=}"
: "${EXPECT_THUMBS_FSTYPES:=}"
: "${EXPECT_PHOTO_FSTYPES:=}"

is_truthy() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

csv_has() {
  csv="$1"
  needle="$2"
  old_ifs="$IFS"
  IFS=','
  for item in $csv; do
    clean="$(printf '%s' "$item" | tr -d '[:space:]')"
    if [ "$clean" = "$needle" ]; then
      IFS="$old_ifs"
      return 0
    fi
  done
  IFS="$old_ifs"
  return 1
}

ensure_absolute_dir() {
  path="$1"
  label="$2"
  if [ -z "$path" ]; then
    echo "ERROR: ${label} is empty."
    exit 1
  fi
  case "$path" in
    /*) ;;
    *)
      echo "ERROR: ${label} must be an absolute path, got: ${path}"
      exit 1
      ;;
  esac
  mkdir -p "$path"
  if [ ! -d "$path" ]; then
    echo "ERROR: Could not create/read directory for ${label}: ${path}"
    exit 1
  fi
}

assert_writable() {
  path="$1"
  label="$2"
  probe="${path}/.fjordlens_write_test.$$"
  if ! ( : > "$probe" ) 2>/dev/null; then
    echo "ERROR: ${label} is not writable: ${path}"
    exit 1
  fi
  rm -f "$probe" >/dev/null 2>&1 || true
}

mount_field() {
  path="$1"
  field="$2"
  findmnt -T "$path" -n -o "$field" 2>/dev/null | head -n 1 || true
}

report_mount() {
  path="$1"
  label="$2"
  expected_csv="$3"
  target="$(mount_field "$path" TARGET)"
  source="$(mount_field "$path" SOURCE)"
  fstype="$(mount_field "$path" FSTYPE)"
  if [ -z "$target" ] || [ -z "$fstype" ]; then
    echo "ERROR: Could not resolve mount info for ${label}: ${path}"
    exit 1
  fi
  echo "    ${label}: ${path}"
  echo "      mount: ${source} on ${target} (fstype=${fstype})"
  if [ -n "$expected_csv" ] && ! csv_has "$expected_csv" "$fstype"; then
    echo "ERROR: ${label} fstype '${fstype}' is not in EXPECT list: ${expected_csv}"
    exit 1
  fi
}

echo "==> FjordLens bootstrap"
echo "    Repo: ${REPO_DIR}"
echo "    Env : ${ENV_FILE}"

ensure_absolute_dir "$DATA_DIR" "DATA_DIR"
ensure_absolute_dir "$UPLOADS_HOST_DIR" "UPLOADS_HOST_DIR"
ensure_absolute_dir "$THUMBS_HOST_DIR" "THUMBS_HOST_DIR"

# Ensure expected app subfolders exist up front.
mkdir -p "${UPLOADS_HOST_DIR}/originals" "${UPLOADS_HOST_DIR}/converted"

assert_writable "$DATA_DIR" "DATA_DIR"
assert_writable "$UPLOADS_HOST_DIR" "UPLOADS_HOST_DIR"
assert_writable "$THUMBS_HOST_DIR" "THUMBS_HOST_DIR"

echo "==> Mount preflight"
report_mount "$DATA_DIR" "DATA_DIR" "$EXPECT_DATA_FSTYPES"
report_mount "$UPLOADS_HOST_DIR" "UPLOADS_HOST_DIR" "$EXPECT_UPLOADS_FSTYPES"
report_mount "$THUMBS_HOST_DIR" "THUMBS_HOST_DIR" "$EXPECT_THUMBS_FSTYPES"

if is_truthy "$ENABLE_LIBRARY_SOURCE"; then
  if [ -z "${PHOTO_DIR:-}" ]; then
    echo "ERROR: ENABLE_LIBRARY_SOURCE=1 requires PHOTO_DIR in ${ENV_FILE}"
    exit 1
  fi
  if [ ! -d "$PHOTO_DIR" ]; then
    echo "ERROR: PHOTO_DIR does not exist: ${PHOTO_DIR}"
    exit 1
  fi
  report_mount "$PHOTO_DIR" "PHOTO_DIR" "$EXPECT_PHOTO_FSTYPES"
else
  echo "    PHOTO_DIR check skipped (ENABLE_LIBRARY_SOURCE=${ENABLE_LIBRARY_SOURCE})"
fi

echo "==> Starting containers"
cd "$REPO_DIR"
docker compose up -d --build

echo "==> Done"
echo "    Open: http://localhost:${APP_PORT:-9080}"
