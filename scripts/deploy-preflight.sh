#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/ops/.env.production}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

set -a
. "$ENV_FILE"
set +a

require_var() {
  name="$1"
  value="$(printenv "$name" || true)"
  if [ -z "$value" ]; then
    echo "Missing required setting: $name" >&2
    exit 1
  fi
}

require_var APP_DOMAIN
require_var AUTH_PASSWORD
require_var AUTH_SECRET
require_var CORS_ORIGINS
require_var ALLOWED_HOSTS

if [ "${LITESTREAM_REPLICA_URL:-}" = "" ]; then
  echo "LITESTREAM_REPLICA_URL is blank. Deploy will work, but off-host replication is disabled." >&2
fi

echo "Deployment preflight passed for $APP_DOMAIN"
