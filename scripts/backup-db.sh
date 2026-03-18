#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="$ROOT_DIR/backend/.venv/bin/python"
export PYTHONPATH="$ROOT_DIR/backend"

STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
BACKUP_DIR="${1:-$ROOT_DIR/backend/backups}"
DATABASE_URL="$("$PYTHON_BIN" -c 'from app.core.config import get_settings; print(get_settings().portfolio_db_url)')"
DATABASE_BACKEND="$("$PYTHON_BIN" -c 'from app.core.config import get_settings; print(get_settings().database_backend)')"

mkdir -p "$BACKUP_DIR"
if [ "$DATABASE_BACKEND" = "sqlite" ]; then
  DB_PATH="$("$PYTHON_BIN" -c 'from app.core.config import get_settings; from app.ops.sqlite_backup import sqlite_path_from_url; print(sqlite_path_from_url(get_settings().portfolio_db_url))')"
  OUTPUT_PATH="$BACKUP_DIR/portfolio-$STAMP.db"
  "$PYTHON_BIN" -m app.ops.sqlite_backup backup --source "$DB_PATH" --output "$OUTPUT_PATH"
  exit 0
fi

OUTPUT_PATH="$BACKUP_DIR/portfolio-$STAMP.json"
"$PYTHON_BIN" -m app.ops.database_portability snapshot --database-url "$DATABASE_URL" --output "$OUTPUT_PATH"
