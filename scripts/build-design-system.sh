#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

exec "$ROOT_DIR/scripts/use-local-node.sh" npm --prefix "$ROOT_DIR/design-system" run build
