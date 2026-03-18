#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
WORK_DIR="${1:-$(mktemp -d /tmp/portfolio-litestream.XXXXXX)}"
LITESTREAM_BIN="${LITESTREAM_BIN:-$ROOT_DIR/.tools/litestream/litestream}"
PRIMARY_DB="$WORK_DIR/portfolio.db"
REPLICA_PATH="$WORK_DIR/portfolio-replica.db"
RESTORE_DB="$WORK_DIR/portfolio-restored.db"
CONFIG_PATH="$WORK_DIR/litestream.yml"
VALIDATION_MARKER="Replica Validation Account"

if [ ! -x "$LITESTREAM_BIN" ]; then
  echo "Litestream binary not found at $LITESTREAM_BIN" >&2
  exit 1
fi

mkdir -p "$WORK_DIR"
cat > "$CONFIG_PATH" <<EOF
dbs:
  - path: $PRIMARY_DB
    replica:
      path: $REPLICA_PATH
EOF

export PYTHONPATH="$ROOT_DIR/backend"
export PORTFOLIO_DB_URL="sqlite:///$PRIMARY_DB"
export ENABLE_SCHEDULER=false

"$ROOT_DIR/backend/.venv/bin/python" -m app.demo_seed >/dev/null
"$LITESTREAM_BIN" replicate -config "$CONFIG_PATH" -once -force-snapshot >/dev/null

"$ROOT_DIR/backend/.venv/bin/python" - <<PY
import sqlite3

connection = sqlite3.connect("$PRIMARY_DB")
connection.execute(
    "INSERT INTO accounts (name, account_type, category, brokerage) VALUES (?, ?, ?, ?)",
    ("$VALIDATION_MARKER", "Validation Account", "brokerage", "Litestream"),
)
connection.commit()
connection.close()
PY

"$LITESTREAM_BIN" replicate -config "$CONFIG_PATH" -once >/dev/null
"$LITESTREAM_BIN" restore -config "$CONFIG_PATH" -o "$RESTORE_DB" "$PRIMARY_DB" >/dev/null

"$ROOT_DIR/backend/.venv/bin/python" - <<PY
import json
import sqlite3
import sys


def collect(path: str) -> dict[str, object]:
    with sqlite3.connect(path) as connection:
        tables = {
            "accounts": connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
            "holdings": connection.execute("SELECT COUNT(*) FROM holdings").fetchone()[0],
            "transactions": connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0],
            "price_history": connection.execute("SELECT COUNT(*) FROM price_history").fetchone()[0],
        }
        marker = connection.execute(
            "SELECT COUNT(*) FROM accounts WHERE name = ?",
            ("$VALIDATION_MARKER",),
        ).fetchone()[0]
    return {"tables": tables, "marker_present": bool(marker)}


primary = collect("$PRIMARY_DB")
restored = collect("$RESTORE_DB")

if primary != restored:
    print(json.dumps({"primary": primary, "restored": restored}, indent=2))
    sys.exit("Litestream restore did not match the primary database.")

print(json.dumps({"work_dir": "$WORK_DIR", "primary": primary, "restored": restored}, indent=2))
PY
