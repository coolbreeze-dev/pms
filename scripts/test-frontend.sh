#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
"$ROOT_DIR/scripts/build-design-system.sh"
cd "$ROOT_DIR/frontend"

exec "$ROOT_DIR/scripts/use-local-node.sh" npm test
