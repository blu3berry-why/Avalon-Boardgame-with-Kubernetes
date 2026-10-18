#!/usr/bin/env bash
# Black-box check of the api-gateway spec (openspec/specs/api-gateway) against a
# running stack. Registers a throwaway user on each run.
#
#   tests/gateway_smoke.sh http://localhost:48080
#   tests/gateway_smoke.sh https://avalon.blu3berry.com
set -u
BASE="${1:?usage: $0 <base-url>}"
BASE="${BASE%/}"
HDR="Avalon-Header-Logged-In-User-Username"
USER_NAME="smoke-$(date +%s)-$RANDOM"
PASSWORD="smoke-pw-$RANDOM"
FAILED=0

check() { # check <name> <expected> <actual>
  if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1 (expected $2, got $3)"; FAILED=1; fi
}
status() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
body() { curl -s "$@"; }

check "health without a token"            200 "$(status "$BASE/")"
check "register through the gateway"      200 "$(status -X POST -H 'Content-Type: application/json' \
  -d "{\"username\":\"$USER_NAME\",\"password\":\"$PASSWORD\"}" "$BASE/register")"

LOGIN=$(body -X POST -H 'Content-Type: application/json' \
  -d "{\"username\":\"$USER_NAME\",\"password\":\"$PASSWORD\"}" "$BASE/login")
TOKEN=$(printf '%s' "$LOGIN" | sed -n 's/.*"token": *"\([^"]*\)".*/\1/p')
check "login returns a token"             yes "$([ -n "$TOKEN" ] && echo yes || echo no)"

check "protected route without a token"   401 "$(status -X POST "$BASE/lobby/create")"
check "protected route with garbage token" 401 "$(status -X POST -H 'Authorization: Bearer not-a-jwt' "$BASE/lobby/create")"
check "forged identity without a token"   401 "$(status -H "$HDR: bob" "$BASE/tryheader")"
check "protected route with a token"      200 "$(status -X POST -H "Authorization: Bearer $TOKEN" "$BASE/lobby/create")"

# /tryheader echoes the identity the game service received.
ECHO=$(body -H "Authorization: Bearer $TOKEN" -H "$HDR: bob" "$BASE/tryheader")
check "identity comes from the token, not the client" yes \
  "$(printf '%s' "$ECHO" | grep -q "\"$USER_NAME\"" && ! printf '%s' "$ECHO" | grep -q '"bob"' && echo yes || echo no)"

[ "$FAILED" = 0 ] && echo "ALL PASS" || { echo "SOME CHECKS FAILED"; exit 1; }
