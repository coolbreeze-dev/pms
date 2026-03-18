#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REMOTE_NAME="${1:-origin}"

cd "$ROOT_DIR"

remote_url="$(git remote get-url "$REMOTE_NAME" 2>/dev/null || true)"
if [ -z "$remote_url" ]; then
  echo "No git remote named '$REMOTE_NAME' was found." >&2
  echo "Create a GitHub repo, add it as '$REMOTE_NAME', and run this script again." >&2
  exit 1
fi

case "$remote_url" in
  git@github.com:*)
    repo_url="https://github.com/${remote_url#git@github.com:}"
    ;;
  git@gitlab.com:*)
    repo_url="https://gitlab.com/${remote_url#git@gitlab.com:}"
    ;;
  git@bitbucket.org:*)
    repo_url="https://bitbucket.org/${remote_url#git@bitbucket.org:}"
    ;;
  https://github.com/*|https://gitlab.com/*|https://bitbucket.org/*)
    repo_url="$remote_url"
    ;;
  *)
    echo "Unsupported remote URL format: $remote_url" >&2
    exit 1
    ;;
esac

repo_url="${repo_url%.git}"

printf 'https://dashboard.render.com/blueprint/new?repo=%s\n' "$repo_url"
