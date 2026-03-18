#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
CACHE_DIR="${TMPDIR:-/tmp}/harbor-design-system-npm-cache"

mkdir -p "$CACHE_DIR"

export npm_config_cache="$CACHE_DIR"

exec "$ROOT_DIR/scripts/use-local-node.sh" npm --prefix "$ROOT_DIR/design-system" run pack:check
