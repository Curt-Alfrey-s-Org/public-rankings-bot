#!/usr/bin/env bash
# Scrape real WPBA/WPA (and optional Fargo) data.
# From project root: ./scripts/scrape_and_test.sh
# REFRESH_VERBOSE=1 for scraper logs. SKIP_FARGO=1 to skip Fargo.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== 1. Scraping WPBA + WPA rankings ==="
REFRESH_VERBOSE="${REFRESH_VERBOSE:-1}" python3 scripts/refresh_rankings.py
echo ""

if [[ "${SKIP_FARGO:-0}" != "1" ]]; then
  echo "=== 2. Fargo sync ==="
  REFRESH_VERBOSE=1 python3 scripts/refresh_fargo.py || true
  echo ""
else
  echo "=== 2. Fargo skipped (SKIP_FARGO=1) ==="
fi

echo "Done. Try GET /api/rankings?org=WPBA to verify."
