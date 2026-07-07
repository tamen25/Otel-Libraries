#!/usr/bin/env sh
# Continuously drives the python entry service; ignores early failures.
TARGET="${TARGET:-http://python-app:8000/order}"
echo "loadgen -> $TARGET"
while true; do
  curl -s -o /dev/null -w "order: %{http_code}\n" "$TARGET" || echo "order: retry"
  sleep 3
done
