#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR/frontend"

exec "$ROOT_DIR/scripts/use-local-node.sh" npm run test:e2e
