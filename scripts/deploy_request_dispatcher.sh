#!/usr/bin/env bash
# Host-side deploy request dispatcher for Admin "Update website" / "Full deploy".
#
# Why: the internet-facing API container must never hold /var/run/docker.sock
# (docker-group/socket access is root-equivalent on the host — Docker Engine
# security docs: https://docs.docker.com/engine/security/#docker-daemon-attack-surface).
# Instead the API writes a small JSON request file into logs/deploy-requests/
# (shared via the ../logs:/app/logs bind mount) and this script — run on the
# Docker host by the systemd path/oneshot pair in production/systemd/ — consumes
# the queue and runs the matching repo script. See docs/ADMIN_DEPLOY_HOST_DISPATCH.md.
#
# Usage:  scripts/deploy_request_dispatcher.sh            (normally via systemd)
# Env:    DEPLOY_SITE_MODE   site mode for full_deploy.sh (default: production)
#
# Allowlisted actions (anything else is logged and discarded — request file
# content is data, never executed):
#   rebuild_website -> scripts/rebuild_website_now.sh   (log: logs/rebuild_website.log)
#   full_deploy     -> scripts/full_deploy.sh --no-cache (log: logs/full_deploy.log)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REQUEST_DIR="$APP_ROOT/logs/deploy-requests"
DISPATCH_LOG="$APP_ROOT/logs/deploy_dispatcher.log"
LOCK_FILE="$APP_ROOT/logs/deploy-requests/.dispatcher.lock"

mkdir -p "$REQUEST_DIR"

log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >> "$DISPATCH_LOG"; }

# Single dispatcher at a time (systemd already serializes oneshot activations;
# flock is defense in depth for manual runs). flock(1): non-blocking, exit if held.
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "Another dispatcher run holds the lock; exiting."
  exit 0
fi

# Append the live-log "Done in Xs." footer the streaming endpoints watch for
# (api/services/live_log.py / GET /rebuild-all-images/log stop on this marker).
finish_log() { # <log_file> <start_epoch> <status: ok|failed>
  local lf="$1" start="$2" status="$3" elapsed
  elapsed=$(( $(date +%s) - start ))
  if [ "$status" = "ok" ]; then
    echo "" >> "$lf"
    echo "[$(date -u '+%H:%M:%S')] Done in ${elapsed}s." >> "$lf"
  else
    echo "" >> "$lf"
    echo "[$(date -u '+%H:%M:%S')] Done in ${elapsed}s (with errors)." >> "$lf"
  fi
}

shopt -s nullglob
for req in "$REQUEST_DIR"/*.request; do
  # Parse the action field only; consume (delete) the request before running so
  # a re-triggered path unit never double-runs the same request.
  action="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("action",""))' "$req" 2>/dev/null || true)"
  requested_by="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("requested_by",""))' "$req" 2>/dev/null || true)"
  rm -f -- "$req"
  log "Request: action=${action:-<unparseable>} requested_by=${requested_by:-?} file=$(basename "$req")"

  case "$action" in
    rebuild_website)
      start=$(date +%s)
      # rebuild_website_now.sh appends to REBUILD_WEBSITE_LOG itself and writes
      # its own "Done in Xs." footer; only add ours on failure.
      if REBUILD_WEBSITE_LOG="$APP_ROOT/logs/rebuild_website.log" \
         bash "$SCRIPT_DIR/rebuild_website_now.sh"; then
        log "rebuild_website OK ($(( $(date +%s) - start ))s)"
      else
        log "rebuild_website FAILED ($(( $(date +%s) - start ))s) — see logs/rebuild_website.log"
        finish_log "$APP_ROOT/logs/rebuild_website.log" "$start" failed
      fi
      ;;
    full_deploy)
      start=$(date +%s)
      lf="$APP_ROOT/logs/full_deploy.log"
      if DEPLOY_SITE_MODE="${DEPLOY_SITE_MODE:-production}" \
         bash "$SCRIPT_DIR/full_deploy.sh" --no-cache >> "$lf" 2>&1; then
        log "full_deploy OK ($(( $(date +%s) - start ))s)"
        finish_log "$lf" "$start" ok
      else
        log "full_deploy FAILED ($(( $(date +%s) - start ))s) — see logs/full_deploy.log"
        finish_log "$lf" "$start" failed
      fi
      ;;
    *)
      log "Ignored unknown action '${action}' (allowlist: rebuild_website, full_deploy)"
      ;;
  esac
done
