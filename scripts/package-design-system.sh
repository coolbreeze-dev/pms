#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PACKAGE_DIR="$ROOT_DIR/design-system"
ARTIFACT_DIR="$PACKAGE_DIR/artifacts"
CACHE_DIR="${TMPDIR:-/tmp}/harbor-design-system-npm-cache"

NAME="$("$ROOT_DIR/scripts/use-local-node.sh" node -p "JSON.parse(require('fs').readFileSync(process.argv[1], 'utf8')).name" "$PACKAGE_DIR/package.json")"
VERSION="$("$ROOT_DIR/scripts/use-local-node.sh" node -p "JSON.parse(require('fs').readFileSync(process.argv[1], 'utf8')).version" "$PACKAGE_DIR/package.json")"
BASENAME="$NAME-$VERSION"

mkdir -p "$ARTIFACT_DIR" "$CACHE_DIR"
rm -f "$ARTIFACT_DIR/$BASENAME.tgz" "$ARTIFACT_DIR/$BASENAME.zip"

"$ROOT_DIR/scripts/build-design-system.sh"

(
  cd "$PACKAGE_DIR"
  export npm_config_cache="$CACHE_DIR"
  "$ROOT_DIR/scripts/use-local-node.sh" npm pack --pack-destination "$ARTIFACT_DIR"
)

STAGE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/harbor-design-system.XXXXXX")"
STAGE_DIR="$STAGE_ROOT/$BASENAME"
mkdir -p "$STAGE_DIR"

cp "$PACKAGE_DIR/README.md" "$STAGE_DIR/"
cp "$PACKAGE_DIR/package.json" "$STAGE_DIR/"
cp -R "$PACKAGE_DIR/dist" "$STAGE_DIR/"

ditto -c -k --sequesterRsrc --keepParent "$STAGE_DIR" "$ARTIFACT_DIR/$BASENAME.zip"
rm -rf "$STAGE_ROOT"

printf 'Created package artifacts:\n%s\n%s\n' \
  "$ARTIFACT_DIR/$BASENAME.tgz" \
  "$ARTIFACT_DIR/$BASENAME.zip"
