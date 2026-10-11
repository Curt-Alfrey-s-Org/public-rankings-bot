#!/usr/bin/env bash
# Run migration (add fargo_rating_history, etc.) and EST seed from placement.
# Requires DATABASE_URL. Run from project root or pass path to .env.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
if [ -n "$1" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$1"
  set +a
elif [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  set +a
fi
if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL not set. Source .env or pass its path: $0 /path/to/.env"
  exit 1
fi
echo "Running: alembic upgrade head"
alembic upgrade head
echo "Running: seed_est_from_placement.py"
PYTHONPATH="$ROOT" python3 scripts/seed_est_from_placement.py
