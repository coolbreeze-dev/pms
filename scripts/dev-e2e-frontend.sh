#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
FRONTEND_PORT="${PORTFOLIO_FRONTEND_PORT:-4173}"

"$ROOT_DIR/scripts/build-design-system.sh"
cd "$ROOT_DIR/frontend"

VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://127.0.0.1:8000}" \
  "$ROOT_DIR/scripts/use-local-node.sh" npm run build >/dev/null

exec "$ROOT_DIR/scripts/use-local-node.sh" npm run preview -- --host 127.0.0.1 --port "$FRONTEND_PORT"
