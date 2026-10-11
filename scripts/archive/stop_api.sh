#!/usr/bin/env bash
# Stop the Rankings Bot API (process on port; default 8003).
# Run from project root or scripts/.

set -e
PORT="${API_PORT:-8003}"
pid=$(lsof -t -i :$PORT 2>/dev/null || true)
if [ -z "$pid" ]; then
  echo "Nothing running on port $PORT."
  exit 0
fi
kill "$pid"
echo "Stopped API (PID $pid) on port $PORT."
