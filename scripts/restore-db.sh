#!/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "Usage: ./scripts/restore-db.sh /path/to/backup.db-or-snapshot.json [target]" >&2
  exit 1
fi

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="$ROOT_DIR/backend/.venv/bin/python"
export PYTHONPATH="$ROOT_DIR/backend"

BACKUP_PATH="$1"
DATABASE_URL="$("$PYTHON_BIN" -c 'from app.core.config import get_settings; print(get_settings().portfolio_db_url)')"
DATABASE_BACKEND="$("$PYTHON_BIN" -c 'from app.core.config import get_settings; print(get_settings().database_backend)')"

case "$BACKUP_PATH" in
  *.json)
    TARGET_DATABASE_URL="${2:-$DATABASE_URL}"
    "$PYTHON_BIN" -m app.ops.database_portability restore --database-url "$TARGET_DATABASE_URL" --snapshot "$BACKUP_PATH" --truncate
    ;;
  *)
    if [ "$DATABASE_BACKEND" != "sqlite" ]; then
      echo "Binary .db restores are only supported when the current app database is SQLite. Use a .json snapshot for Postgres/Neon restores." >&2
      exit 1
    fi
    TARGET_PATH="${2:-$("$PYTHON_BIN" -c 'from app.core.config import get_settings; from app.ops.sqlite_backup import sqlite_path_from_url; print(sqlite_path_from_url(get_settings().portfolio_db_url))')}"
    "$PYTHON_BIN" -m app.ops.sqlite_backup restore --backup "$BACKUP_PATH" --target "$TARGET_PATH"
    ;;
esac
