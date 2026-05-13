#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

if [ -z "${APP_DIR:-}" ]; then
	if [ -f "$REPO_DIR/docker-compose.yml" ]; then
		APP_DIR="$REPO_DIR"
	elif [ -f "./docker-compose.yml" ]; then
		APP_DIR="$(pwd)"
	else
		APP_DIR="/volume1/docker/fjordlens"
	fi
fi

SERVICE_NAME="${SERVICE_NAME:-fjordlens}"
REPO_BRANCH="${REPO_BRANCH:-}"
WAIT_TIMEOUT_SEC="${WAIT_TIMEOUT_SEC:-180}"
WAIT_INTERVAL_SEC="${WAIT_INTERVAL_SEC:-2}"
DO_BUILD=1
NO_CACHE=0
SKIP_DB_BACKUP=0
SHOW_LOGS=1
PRUNE_DOCKER=1

usage() {
	cat <<EOF
Usage: $0 [options]

Normal FjordLens update:
  - backs up .env and fjordlens.db when possible
  - pulls the current Git branch with --ff-only
  - runs docker compose up -d --build
  - waits for /api/health

Options:
  --app-dir DIR        FjordLens app directory (default: auto, then /volume1/docker/fjordlens)
  --branch BRANCH     Git branch to pull (default: current branch, then main)
  --no-build          Do not build images; only docker compose up -d
  --no-cache          Rebuild images without Docker cache
  --no-prune          Skip Docker prune before update
  --skip-db-backup    Skip SQLite backup before updating
  --no-logs           Do not print recent container logs at the end
  -h, --help          Show this help

Environment:
  APP_DIR, REPO_BRANCH, SERVICE_NAME, WAIT_TIMEOUT_SEC, WAIT_INTERVAL_SEC
EOF
}

while [ "$#" -gt 0 ]; do
	case "$1" in
		--app-dir)
			if [ "$#" -lt 2 ]; then
				echo "Fejl: --app-dir mangler en mappe."
				exit 1
			fi
			shift
			APP_DIR="$1"
			;;
		--branch)
			if [ "$#" -lt 2 ]; then
				echo "Fejl: --branch mangler et branch-navn."
				exit 1
			fi
			shift
			REPO_BRANCH="$1"
			;;
		--no-build)
			DO_BUILD=0
			;;
		--no-cache)
			NO_CACHE=1
			DO_BUILD=1
			;;
		--no-prune)
			PRUNE_DOCKER=0
			;;
		--skip-db-backup)
			SKIP_DB_BACKUP=1
			;;
		--no-logs)
			SHOW_LOGS=0
			;;
		-h|--help)
			usage
			exit 0
			;;
		*)
			echo "Fejl: ukendt option: $1"
			usage
			exit 1
			;;
	esac
	shift
done

need_cmd() {
	if ! command -v "$1" >/dev/null 2>&1; then
		echo "Fejl: $1 blev ikke fundet i PATH."
		exit 1
	fi
}

validate_wait_settings() {
	case "$WAIT_TIMEOUT_SEC" in
		*[!0-9]*|"") WAIT_TIMEOUT_SEC=180 ;;
	esac
	case "$WAIT_INTERVAL_SEC" in
		*[!0-9]*|"") WAIT_INTERVAL_SEC=2 ;;
	esac
	if [ "$WAIT_TIMEOUT_SEC" -le 0 ]; then
		WAIT_TIMEOUT_SEC=180
	fi
	if [ "$WAIT_INTERVAL_SEC" -le 0 ]; then
		WAIT_INTERVAL_SEC=2
	fi
}

docker_compose() {
	if [ -n "${DOCKER_SUDO:-}" ]; then
		sudo docker compose "$@"
	else
		docker compose "$@"
	fi
}

docker_cmd() {
	if [ -n "${DOCKER_SUDO:-}" ]; then
		sudo docker "$@"
	else
		docker "$@"
	fi
}

prune_docker_space() {
	if [ "$PRUNE_DOCKER" != "1" ]; then
		return 0
	fi

	echo "==> Rydder Docker build-cache og ubrugte objekter (bevarer volumes/data)"
	docker_cmd builder prune -af || true
	docker_cmd image prune -af || true
	docker_cmd container prune -f || true
	docker_cmd network prune -f || true
	docker_cmd system df || true
}

read_env_value() {
	key="$1"
	file="$APP_DIR/.env"
	[ -f "$file" ] || return 1
	line="$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$file" | tail -n 1 || true)"
	[ -n "$line" ] || return 1
	value="${line#*=}"
	printf '%s' "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//;s/^"//;s/"$//'
}

backup_env_file() {
	data_dir="${DATA_DIR:-$(read_env_value DATA_DIR || printf '%s' '/volume1/docker/fjordlens/data')}"
	backup_dir="$data_dir/backups"
	if [ ! -f "$APP_DIR/.env" ]; then
		return 0
	fi
	if mkdir -p "$backup_dir" 2>/dev/null; then
		backup_path="$backup_dir/fjordlens.env.$TS.bak"
		cp -p "$APP_DIR/.env" "$backup_path"
		echo "==> .env backup: $backup_path"
	else
		backup_path="$APP_DIR/.env.bak.$TS"
		cp -p "$APP_DIR/.env" "$backup_path"
		echo "==> .env backup: $backup_path"
	fi
}

backup_database_from_container() {
	container_id="$(docker_compose ps -q "$SERVICE_NAME" 2>/dev/null || true)"
	[ -n "$container_id" ] || return 1
	state="$(docker_cmd inspect --format '{{.State.Status}}' "$container_id" 2>/dev/null || true)"
	[ "$state" = "running" ] || return 1

	docker_compose exec -T "$SERVICE_NAME" sh -s <<EOF
set -eu
mkdir -p /data/backups
python - <<PY
import os
import sqlite3

src = "/data/fjordlens.db"
dst = "/data/backups/fjordlens.db.$TS.bak"
if not os.path.exists(src):
    print("Ingen database at backupe endnu")
    raise SystemExit(0)

source = sqlite3.connect(src)
target = sqlite3.connect(dst)
try:
    with target:
        source.backup(target)
finally:
    target.close()
    source.close()
print(dst)
PY
EOF
}

backup_database_from_host() {
	data_dir="${DATA_DIR:-$(read_env_value DATA_DIR || printf '%s' '/volume1/docker/fjordlens/data')}"
	db_path="$data_dir/fjordlens.db"
	backup_dir="$data_dir/backups"
	if [ ! -f "$db_path" ]; then
		echo "==> Ingen database fundet til backup endnu: $db_path"
		return 0
	fi
	mkdir -p "$backup_dir"
	backup_path="$backup_dir/fjordlens.db.$TS.bak"
	cp -p "$db_path" "$backup_path"
	echo "==> Database backup: $backup_path"
}

backup_database() {
	if [ "$SKIP_DB_BACKUP" = "1" ]; then
		echo "==> Springer database-backup over"
		return 0
	fi
	echo "==> Tager database-backup"
	if backup_database_from_container; then
		return 0
	fi
	backup_database_from_host
}

wait_for_fjordlens() {
	elapsed=0
	echo "==> Venter paa FjordLens health (timeout ${WAIT_TIMEOUT_SEC}s)"
	while [ "$elapsed" -lt "$WAIT_TIMEOUT_SEC" ]; do
		container_id="$(docker_compose ps -q "$SERVICE_NAME" 2>/dev/null || true)"
		if [ -n "$container_id" ]; then
			state="$(docker_cmd inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
			case "$state" in
				healthy|running)
					if docker_compose exec -T "$SERVICE_NAME" sh -lc "curl -fsS http://127.0.0.1:8080/api/health >/dev/null"; then
						echo "==> FjordLens er klar"
						return 0
					fi
					;;
				unhealthy|exited|dead)
					echo "Fejl: FjordLens status er $state under opstart."
					docker_compose logs --tail=120 || true
					return 1
					;;
			esac
		fi
		sleep "$WAIT_INTERVAL_SEC"
		elapsed=$((elapsed + WAIT_INTERVAL_SEC))
	done

	echo "Fejl: timeout mens FjordLens blev klar."
	docker_compose ps || true
	docker_compose logs --tail=120 || true
	return 1
}

need_cmd docker
need_cmd git
validate_wait_settings

DOCKER_SUDO=""
if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
	if ! docker info >/dev/null 2>&1; then
		DOCKER_SUDO="sudo"
	fi
fi

if [ ! -d "$APP_DIR" ]; then
	echo "Fejl: APP_DIR findes ikke: $APP_DIR"
	exit 1
fi

if [ ! -f "$APP_DIR/docker-compose.yml" ]; then
	echo "Fejl: docker-compose.yml blev ikke fundet i APP_DIR: $APP_DIR"
	exit 1
fi

cd "$APP_DIR" || exit 1
TS="$(date +%Y%m%d-%H%M%S)"

echo "==> App directory: $APP_DIR"
docker_compose config >/dev/null

if [ ! -d .git ]; then
	echo "Fejl: $APP_DIR er ikke et git repository."
	echo "Tip: kontroller APP_DIR, eller klon FjordLens repoet igen i denne mappe."
	exit 1
fi

dirty="$(git status --porcelain --untracked-files=no)"
if [ -n "$dirty" ]; then
	echo "Fejl: der er lokale tracked aendringer i $APP_DIR."
	echo "Commit/stash dem foerst, eller ret mappen manuelt foer update koeres igen."
	git status --short --untracked-files=no
	exit 1
fi

if [ -z "$REPO_BRANCH" ]; then
	REPO_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
	if [ -z "$REPO_BRANCH" ] || [ "$REPO_BRANCH" = "HEAD" ]; then
		REPO_BRANCH="main"
	fi
fi

OLD_REV="$(git rev-parse HEAD 2>/dev/null || true)"

backup_env_file
backup_database

echo "==> Henter seneste kode fra origin/$REPO_BRANCH"
git fetch origin "$REPO_BRANCH"
git merge --ff-only "origin/$REPO_BRANCH"

NEW_REV="$(git rev-parse HEAD 2>/dev/null || true)"
if [ -n "$OLD_REV" ] && [ "$OLD_REV" = "$NEW_REV" ]; then
	echo "==> Ingen nye commits. Sikrer at containerne koerer."
else
	echo "==> Opdateret: ${OLD_REV:-unknown} -> $NEW_REV"
fi

prune_docker_space

if [ "$NO_CACHE" = "1" ]; then
	echo "==> Bygger uden Docker cache"
	docker_compose build --no-cache
	echo "==> Starter FjordLens"
	docker_compose up -d
elif [ "$DO_BUILD" = "1" ]; then
	echo "==> Bygger og starter FjordLens"
	docker_compose up -d --build
else
	echo "==> Starter FjordLens uden build"
	docker_compose up -d
fi

wait_for_fjordlens

echo "==> Status"
docker_compose ps

if [ "$SHOW_LOGS" = "1" ]; then
	echo "==> Seneste logs"
	docker_compose logs --tail=50
fi
