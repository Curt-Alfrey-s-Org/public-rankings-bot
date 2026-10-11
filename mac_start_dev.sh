#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script must run on macOS."
  exit 1
fi

if [[ ! -d ".git" ]]; then
  echo "Run this from the repo root."
  exit 1
fi

REPO_DIR="$(pwd)"
# Postgres is Docker-only. Use postgres:5432 when API runs in Docker; for host API, run: docker compose run --service-ports api
API_CMD="cd \"${REPO_DIR}\" && source .venv/bin/activate && JWT_SECRET=test-secret DATABASE_URL=postgresql://rankingsbot_user:change-me@postgres:5432/rankingsbot uvicorn api.main:app --reload --host 0.0.0.0 --port 8000"
FRONTEND_CMD="cd \"${REPO_DIR}/frontend\" && npm run dev"
MOBILE_CMD="cd \"${REPO_DIR}/mobile\" && npm start"

if command -v docker >/dev/null; then
  docker compose up -d postgres || true
fi

open "mobile/ios/mobile.xcworkspace"

osascript <<EOF
tell application "Terminal"
  activate
  do script "${API_CMD}"
  do script "${FRONTEND_CMD}"
  do script "${MOBILE_CMD}"
end tell
EOF

echo "Started API, frontend, and Metro in Terminal tabs."
echo "Opened Xcode workspace: mobile/ios/mobile.xcworkspace"
