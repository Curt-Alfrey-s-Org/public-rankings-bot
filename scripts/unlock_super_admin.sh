#!/usr/bin/env bash
# Unlock super admin (tornybotca1) when locked after 5 failed login attempts.
# Run on the server where the API and DB run.
#
# Usage:
#   ./unlock_super_admin.sh
#   ./unlock_super_admin.sh other_username
#
# Prerequisites: DATABASE_URL in .env or environment

set -e
PROJECT_ROOT="${RANKINGS_BOT_ROOT:-/home/ansible/rankings-bot/Rankings-Bot}"
USERNAME="${1:-tornybotca1}"

if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  source "$PROJECT_ROOT/.env" 2>/dev/null || true
  set +a
fi

if [ -z "$DATABASE_URL" ]; then
  echo "ERROR: DATABASE_URL not set. Source .env or set it in the environment."
  exit 1
fi

# Replace postgres host with 127.0.0.1 (for host-side runs)
DB_URL="${DATABASE_URL}"
[[ "$DB_URL" == *"@postgres"* ]] && DB_URL="${DATABASE_URL//@postgres/@127.0.0.1}"

echo "Unlocking user: $USERNAME"
psql "$DB_URL" -c "UPDATE users SET account_locked_until = NULL, failed_login_attempts = 0 WHERE username = '$USERNAME';" 2>/dev/null || \
psql "$DATABASE_URL" -c "UPDATE users SET account_locked_until = NULL, failed_login_attempts = 0 WHERE username = '$USERNAME';"

echo "Done. User $USERNAME is unlocked."
