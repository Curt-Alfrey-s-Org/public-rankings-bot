#!/usr/bin/env bash
# Emit a content hash of the Docker build context (Dockerfile, requirements, app code).
# Used by deploy/start scripts to skip rebuild when nothing changed.
# Tracks all inputs that affect the image per Docker/Python industry standards.
#
# Refs: Docker BuildKit docs, PEP 8, Twelve-Factor App
# Usage: HASH=$(./scripts/docker_build_hash.sh)   # from project root

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

# Hash function (sha256 preferred per Docker/content-addressable standards)
hash_cmd=""
if command -v sha256sum &>/dev/null; then
  hash_cmd="sha256sum"
elif command -v shasum &>/dev/null; then
  hash_cmd="shasum -a 256"
else
  echo "unknown"
  exit 0
fi

# 1. Image definition (Dockerfile, requirements, compose)
#    Change => pip/apt layers invalidated
DEF_FILES=(Dockerfile requirements-api.txt requirements-deps.txt)
[ -f production/docker-compose.prod.yml ] && DEF_FILES+=(production/docker-compose.prod.yml)
DEF_HASH=$(for f in "${DEF_FILES[@]}"; do [ -f "$f" ] && cat "$f"; done | $hash_cmd | awk '{print $1}')

# 2. App code (paths copied by Dockerfile COPY; excludes per .dockerignore)
#    Change => app layer invalidated; deps layers reused (intelligent layering)
APP_DIRS=(api scrapers database scripts alembic)
APP_FILES=(alembic.ini)
# Root .py files (Dockerfile: COPY *.py)
for f in *.py; do
  [ -f "$f" ] && [[ "$f" != test_*.py ]] && [[ "$f" != verify_*.py ]] && [[ "$f" != run_*.py ]] && [[ "$f" != conftest.py ]] && APP_FILES+=("$f")
done

hash_tree() {
  local dirs=("$@")
  find "${dirs[@]}" -type f 2>/dev/null | sort | while IFS= read -r f; do
    # Skip __pycache__, .pyc (matches .dockerignore)
    [[ "$f" == *__pycache__* ]] && continue
    [[ "$f" == *.pyc ]] && continue
    [ -f "$f" ] && $hash_cmd "$f" 2>/dev/null
  done | $hash_cmd | awk '{print $1}'
}

APP_DIR_HASH=$(hash_tree "${APP_DIRS[@]}")
APP_FILES_CONTENT=$(for f in "${APP_FILES[@]}"; do [ -f "$f" ] && cat "$f"; done 2>/dev/null | $hash_cmd | awk '{print $1}')
APP_HASH=$(echo "${APP_DIR_HASH:-empty}${APP_FILES_CONTENT:-empty}" | $hash_cmd | awk '{print $1}')

# 3. Combined hash (any change => rebuild)
echo "${DEF_HASH}${APP_HASH}" | $hash_cmd | awk '{print $1}'
