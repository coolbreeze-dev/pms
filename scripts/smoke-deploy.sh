#!/bin/sh
set -eu

BASE_URL="${1:-http://127.0.0.1:8000}"
PASSWORD="${PORTFOLIO_APP_PASSWORD:-${AUTH_PASSWORD:-}}"

auth_session="$(curl -fsS "$BASE_URL/api/auth/session")"
auth_enabled="$(
  printf '%s' "$auth_session" | python3 -c 'import json,sys; print("true" if json.load(sys.stdin).get("enabled") else "false")'
)"

auth_header=""
if [ "$auth_enabled" = "true" ]; then
  if [ -z "$PASSWORD" ]; then
    echo "Password auth is enabled. Set PORTFOLIO_APP_PASSWORD or AUTH_PASSWORD before running this smoke test." >&2
    exit 1
  fi
  login_payload="$(printf '{"password":"%s"}' "$PASSWORD")"
  login_response="$(curl -fsS -X POST "$BASE_URL/api/auth/login" -H "Content-Type: application/json" -d "$login_payload")"
  token="$(
    printf '%s' "$login_response" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])'
  )"
  auth_header="Authorization: Bearer $token"
fi

curl -fsS "$BASE_URL/api/health" >/dev/null
curl -fsS "$BASE_URL/api/ready" >/dev/null
if [ -n "$auth_header" ]; then
  curl -fsS -H "$auth_header" "$BASE_URL/api/ops/observability" >/dev/null
  curl -fsS -H "$auth_header" "$BASE_URL/api/portfolio?category=brokerage" >/dev/null
else
  curl -fsS "$BASE_URL/api/ops/observability" >/dev/null
  curl -fsS "$BASE_URL/api/portfolio?category=brokerage" >/dev/null
fi
curl -fsS "$BASE_URL/" >/dev/null

printf 'Smoke checks passed for %s\n' "$BASE_URL"
