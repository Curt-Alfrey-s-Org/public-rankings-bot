#!/usr/bin/env bash
# Stop USPBF (WordPress, MySQL, nginx). Optionally stop cf-uspbf.
# Set STOP_TUNNEL=1 to also stop cf-uspbf.
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
. "$ROOT/scripts/compose-plain.sh"

echo "🛑 Stopping USPBF..."

uspbf_compose down

if [ -n "${STOP_TUNNEL:-}" ] && [ "$STOP_TUNNEL" = "1" ]; then
  echo "Stopping cf-uspbf..."
  sudo docker stop cf-uspbf 2>/dev/null || true
fi

echo ""
echo "✅ USPBF stopped"
