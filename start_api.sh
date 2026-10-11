#!/bin/bash
# Start Rankings Bot API (convenience wrapper)
# Run from Rankings-Bot root: ./start_api.sh
# Or from scripts: ./scripts/start_api.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/scripts/start_api.sh"
