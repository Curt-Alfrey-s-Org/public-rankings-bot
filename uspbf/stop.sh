#!/usr/bin/env bash
# Delegates to scripts/stop.sh (canonical entrypoint lives under scripts/).
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/stop.sh"
