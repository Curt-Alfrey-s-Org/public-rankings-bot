#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:-$PWD}"

echo "==> Using repo: ${REPO_DIR}"
cd "${REPO_DIR}"

if [[ ! -d ".git" ]]; then
  echo "Error: run this from the rankings-bot repo root (or pass repo path as arg)."
  exit 1
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Error: this script is for macOS."
  exit 1
fi

echo "==> Checking required tools..."
command -v git >/dev/null || { echo "Missing git"; exit 1; }
command -v node >/dev/null || { echo "Missing node"; exit 1; }
command -v npm >/dev/null || { echo "Missing npm"; exit 1; }
command -v python3 >/dev/null || { echo "Missing python3"; exit 1; }
command -v xcodebuild >/dev/null || { echo "Missing Xcode Command Line Tools"; exit 1; }

echo "==> Backend Python env setup..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
if [[ -f "requirements-api.txt" ]]; then
  pip install -r requirements-api.txt
fi

echo "==> Frontend deps..."
if [[ -d "frontend" ]]; then
  cd frontend
  npm install
  cd ..
fi

echo "==> Mobile deps + iOS pods..."
cd mobile
npm install
npm run ios:setup
cd ..

echo "==> Optional: start postgres via Docker if available..."
if command -v docker >/dev/null; then
  docker compose up -d postgres || true
fi

echo "==> Setup complete."
echo
echo "Next steps:"
echo "1) API terminal:"
echo "   source .venv/bin/activate"
echo "   JWT_SECRET=test-secret DATABASE_URL=postgresql://rankingsbot_user:change-me@postgres:5432/rankingsbot uvicorn api.main:app --reload --host 0.0.0.0 --port 8000"
echo
echo "2) Frontend terminal:"
echo "   cd frontend && npm run dev"
echo
echo "3) iOS terminal:"
echo "   cd mobile && npm start"
echo
echo "4) Xcode:"
echo "   open mobile/ios/mobile.xcworkspace"
