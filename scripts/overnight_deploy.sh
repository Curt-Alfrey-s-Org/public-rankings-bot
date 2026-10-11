#!/usr/bin/env bash
# Overnight full deploy with logging and verification.
# Usage: ./scripts/overnight_deploy.sh
#
# For live API logs while it runs, in another terminal:
#   journalctl -u rankings-bot-api -f

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

mkdir -p logs
LOG="logs/full_deploy_$(date +%Y%m%d_%H%M%S).log"

echo "=== Overnight deploy started $(date -u '+%Y-%m-%d %H:%M:%S') ==="
echo "Log: $LOG"
echo ""

./scripts/full_deploy.sh --no-cache 2>&1 | tee "$LOG"
EXIT=$?

echo ""
echo "=== Deploy finished $(date -u '+%Y-%m-%d %H:%M:%S') exit=$EXIT ==="
echo ""

echo "=== Verification ==="
./scripts/verify_production.sh
echo ""

echo "=== Error summary (if any) ==="
if grep -i -E 'ERROR|FAIL|failed|err "|exit 1' "$LOG" 2>/dev/null | tail -20; then
  echo "(see full log: $LOG)"
else
  echo "None found."
fi

exit "$EXIT"
