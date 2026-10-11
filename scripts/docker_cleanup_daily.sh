#!/usr/bin/env bash
# Daily Docker cleanup: remove unused images and stopped containers.
# Does NOT remove running containers or volumes. Host log files (e.g. rankings-api.log,
# rankings-bot-start.log) are not in Docker — they are never touched.
#
# Optional: prune build cache with DOCKER_PRUNE_BUILD=1.
# Usage: ./scripts/docker_cleanup_daily.sh
# Cron: 0 3 * * * /home/ansible/rankings-bot/Rankings-Bot/scripts/docker_cleanup_daily.sh >> /home/ansible/rankings-bot/Rankings-Bot/docker_cleanup.log 2>&1

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG="${APP_ROOT}/docker_cleanup.log"

# Always use sudo for Docker so the script works without the user being in the docker group
DOCKER="sudo docker"

log() { echo "$(date '+%Y-%m-%d %H:%T') $*"; }

log "=== Docker daily cleanup (keeping log files and running containers) ==="

# Prune stopped containers (keeps running ones; host logs like rankings-api.log are not in Docker)
$DOCKER container prune -f
log "Container prune done."

# Prune dangling/unused images (not used by any container)
$DOCKER image prune -f
log "Image prune done."

# Optional: prune build cache (saves more space, slows next build slightly)
if [ "${DOCKER_PRUNE_BUILD:-0}" = "1" ]; then
  $DOCKER builder prune -f
  log "Builder prune done."
fi

log "=== Cleanup finished ==="
