#!/bin/bash
# Usage: ./race_test.sh request_id cookie_jar
# The cookie jar must belong to the assigned master; request must be assigned.
set -euo pipefail
REQUEST_ID=${1:?Provide an assigned request ID}
COOKIE_JAR=${2:?Provide the assigned master login cookie jar}
URL=${BASE_URL:-http://localhost:8000}
[[ "$REQUEST_ID" =~ ^[1-9][0-9]*$ && -f "$COOKIE_JAR" ]] || exit 2

results=$(mktemp -d)
trap 'rm -rf -- "$results"' EXIT
pids=()
for i in {1..10}; do
  curl --silent --show-error --max-time 20 --output /dev/null --write-out '%{http_code}' \
    --cookie "$COOKIE_JAR" -X POST "$URL/api/requests/$REQUEST_ID/take" > "$results/$i" &
  pids+=("$!")
done
failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || failed=1
done
success=0
conflicts=0
for i in {1..10}; do
  code=$(cat "$results/$i")
  echo "Request $i: HTTP $code"
  case "$code" in
    200) success=$((success + 1));;
    409) conflicts=$((conflicts + 1));;
    *) failed=1;;
  esac
done
[[ "$failed" == 0 && "$success" == 1 && "$conflicts" == 9 ]]
