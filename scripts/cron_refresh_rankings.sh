#!/usr/bin/env bash
# Run rankings refresh for cron. Use same user as the API (e.g. ansible).
# Crontab examples:
#   Every 1 hour:  0 * * * * /home/ansible/rankings-bot/scripts/cron_refresh_rankings.sh >> /home/ansible/rankings-bot/rankings-refresh.log 2>&1
#   Daily at 6 AM: 0 6 * * * /home/ansible/rankings-bot/scripts/cron_refresh_rankings.sh >> /home/ansible/rankings-bot/rankings-refresh.log 2>&1

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."
# Prefer parent rankings-bot venv (has pdfplumber) if present
PARENT_ROOT="$(cd "$SCRIPT_DIR/../.." 2>/dev/null && pwd)"
if [ -x "$SCRIPT_DIR/../venv/bin/python3" ]; then
    exec "$SCRIPT_DIR/../venv/bin/python3" scripts/refresh_rankings.py
fi
if [ -x "$SCRIPT_DIR/../.venv/bin/python3" ]; then
    exec "$SCRIPT_DIR/../.venv/bin/python3" scripts/refresh_rankings.py
fi
if [ -x "$PARENT_ROOT/venv/bin/python3" ]; then
    exec "$PARENT_ROOT/venv/bin/python3" scripts/refresh_rankings.py
fi
exec python3 scripts/refresh_rankings.py
