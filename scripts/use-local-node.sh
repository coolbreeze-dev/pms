#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
export PATH="$ROOT_DIR/.tools/node/bin:$PATH"

exec "$@"
