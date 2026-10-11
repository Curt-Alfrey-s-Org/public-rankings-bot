#!/usr/bin/env bash
# Emit a hash of the frontend build context (deps + config + source mtimes) so
# deploy scripts can skip a redundant frontend build when nothing changed.
# Usage: HASH=$(./scripts/frontend_build_hash.sh)   # from project root
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND="$APP_ROOT/frontend"
cd "$APP_ROOT"

[ ! -d "$FRONTEND" ] && echo "unknown" && exit 0

# Hash inputs that affect build output
_hash_inputs() {
  [ -f "$FRONTEND/package.json" ] && cat "$FRONTEND/package.json"
  [ -f "$FRONTEND/package-lock.json" ] && cat "$FRONTEND/package-lock.json"
  [ -f "$FRONTEND/vite.config.ts" ] && cat "$FRONTEND/vite.config.ts"
  [ -f "$FRONTEND/vite.config.js" ] && cat "$FRONTEND/vite.config.js"
  [ -f "$FRONTEND/index.html" ] && cat "$FRONTEND/index.html"
  # Include mtimes of source files (fast; changes when any source changes)
  if [ -d "$FRONTEND/src" ]; then
    find "$FRONTEND/src" -type f -print0 2>/dev/null | xargs -0 stat -c '%Y %n' 2>/dev/null || \
    find "$FRONTEND/src" -type f -print0 2>/dev/null | xargs -0 stat -f '%m %N' 2>/dev/null || true
  fi
}

if command -v sha256sum &>/dev/null; then
  _hash_inputs | sha256sum | awk '{print $1}'
elif command -v shasum &>/dev/null; then
  _hash_inputs | shasum -a 256 | awk '{print $1}'
else
  _hash_inputs | md5sum 2>/dev/null | awk '{print $1}' || echo "unknown"
fi
