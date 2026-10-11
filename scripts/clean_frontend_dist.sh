#!/usr/bin/env bash
# Remove frontend/dist so a host-user vite build can run. After Docker builds,
# dist/often contains root-owned files → EACCES writing sw.js / assets.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST="$(cd "$SCRIPT_DIR/../frontend" && pwd)/dist"
[ -d "$DIST" ] || exit 0
if rm -rf "$DIST" 2>/dev/null; then
  exit 0
fi
echo "   cleaning frontend/dist with sudo (root-owned artifacts from Docker)..."
sudo rm -rf "$DIST"
