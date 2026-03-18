#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DB_PATH="${PORTFOLIO_E2E_DB_PATH:-/tmp/household-portfolio-e2e.db}"
BACKEND_PORT="${PORTFOLIO_BACKEND_PORT:-8000}"

export PYTHONPATH="$ROOT_DIR/backend"
export PORTFOLIO_DB_URL="sqlite:///$DB_PATH"
export AUTH_PASSWORD="${AUTH_PASSWORD:-open-sesame}"
export CORS_ORIGINS="${CORS_ORIGINS:-[\"http://127.0.0.1:4173\"]}"
export ENABLE_SCHEDULER=false

"$ROOT_DIR/backend/.venv/bin/python" -m app.demo_seed >/dev/null

exec "$ROOT_DIR/backend/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --app-dir "$ROOT_DIR/backend"
