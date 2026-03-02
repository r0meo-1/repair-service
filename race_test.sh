#!/bin/bash
# Race condition test - sends 10 parallel take requests for request ID 1
# Usage: ./race_test.sh [request_id]

REQUEST_ID=${1:-1}
URL="http://localhost:8000"

echo "=== Race Condition Test ==="
echo "Sending 10 parallel take requests for request #$REQUEST_ID"

for i in $(seq 1 10); do
  curl -s -o /dev/null -w "Thread $i: HTTP %{http_code}\n" \
    -X POST "$URL/master/take/$REQUEST_ID" \
    --cookie-jar /tmp/cookie_$i.txt \
    -c /tmp/cookie_$i.txt &
done

wait
echo "=== Done ==="
echo "Checking final request status:"
curl -s "$URL/api/requests/$REQUEST_ID" | python3 -m json.tool 2>/dev/null || echo "Check the dispatcher panel to see status"
