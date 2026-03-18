#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR/backend"
export PYTHONPYCACHEPREFIX=/tmp/pycache

exec "$ROOT_DIR/backend/.venv/bin/pytest" backend/tests -q

