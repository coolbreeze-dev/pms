#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/ops/.env.production}"

docker compose --env-file "$ENV_FILE" -f "$ROOT_DIR/ops/docker-compose.prod.yml" run --rm restore
