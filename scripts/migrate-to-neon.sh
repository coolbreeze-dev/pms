#!/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "Usage: ./scripts/migrate-to-neon.sh \"postgresql://...neon...\" [source_database_url]" >&2
  exit 1
fi

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="$ROOT_DIR/backend/.venv/bin/python"
export PYTHONPATH="$ROOT_DIR/backend"

TARGET_DATABASE_URL="$1"
SOURCE_DATABASE_URL="${2:-sqlite:///$ROOT_DIR/backend/data/portfolio.db}"

"$PYTHON_BIN" -m app.ops.database_portability copy \
  --source-database-url "$SOURCE_DATABASE_URL" \
  --target-database-url "$TARGET_DATABASE_URL" \
  --truncate-target
