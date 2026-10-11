#!/usr/bin/env bash
# Sync all persistent app data to hub SMB share.
# Manual-only: prompts for credentials, mounts, syncs, unmounts.
# The app never has standing access to the NAS.
#
# Prerequisites:
#   - cifs-utils installed (sudo apt install cifs-utils)
#   - rsync installed (sudo apt install rsync)
#
# Usage:
#   ./scripts/sync_to_nas.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

NAS_IP="${NAS_IP:-192.0.2.30}"
NAS_SHARE="${NAS_SHARE:-Rankings_app}"
NAS_MOUNT_POINT="${NAS_MOUNT_POINT:-/mnt/hub-backup}"
LOG_FILE="$PROJECT_ROOT/logs/nas_sync.log"

log() { echo "[$(date -u '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

mkdir -p "$(dirname "$LOG_FILE")"
sudo mkdir -p "$NAS_MOUNT_POINT"

# --- Mount SMB share ---
ALREADY_MOUNTED=false
if mountpoint -q "$NAS_MOUNT_POINT" 2>/dev/null; then
  ALREADY_MOUNTED=true
  log "NAS already mounted at $NAS_MOUNT_POINT"
else
  MOUNT_OPTS="vers=3.0,uid=$(id -u),gid=$(id -g),file_mode=0664,dir_mode=0775"

  echo ""
  echo "=== Rankings App: hub Backup ==="
  echo "Share: //${NAS_IP}/${NAS_SHARE}"
  echo ""
  read -rp "SMB Username: " SMB_USER
  read -rsp "SMB Password: " SMB_PASS
  echo ""
  sudo mount -t cifs "//${NAS_IP}/${NAS_SHARE}" "$NAS_MOUNT_POINT" \
    -o "username=${SMB_USER},password=${SMB_PASS},${MOUNT_OPTS}" || {
    log "ERROR: SMB mount failed (check username/password)"
    exit 1
  }
  log "Mounted //${NAS_IP}/${NAS_SHARE} at $NAS_MOUNT_POINT"
fi

# Verify we can write
if ! touch "$NAS_MOUNT_POINT/.sync_test" 2>/dev/null; then
  log "ERROR: $NAS_MOUNT_POINT is not writable"
  [ "$ALREADY_MOUNTED" = false ] && sudo umount "$NAS_MOUNT_POINT" 2>/dev/null
  exit 1
fi
rm -f "$NAS_MOUNT_POINT/.sync_test"

# --- Rsync data ---
SYNC_ERRORS=0

sync_dir() {
  local src="$1"
  local label="$2"
  if [ ! -d "$src" ]; then
    log "  $label: source $src does not exist, skipping"
    return
  fi
  mkdir -p "$NAS_MOUNT_POINT/$label"
  if rsync --archive --compress --delete --timeout=60 "$src/" "$NAS_MOUNT_POINT/$label/" 2>>"$LOG_FILE"; then
    log "  $label: synced"
  else
    log "  $label: FAILED (rsync exit $?)"
    SYNC_ERRORS=$((SYNC_ERRORS + 1))
  fi
}

log "NAS sync started -> //${NAS_IP}/${NAS_SHARE}"

sync_dir "$PROJECT_ROOT/backups"                 "backups"
sync_dir "$PROJECT_ROOT/config"                  "config"
sync_dir "$PROJECT_ROOT/scraped_data"            "scraped_data"
sync_dir "$PROJECT_ROOT/media"                   "media"
sync_dir "$PROJECT_ROOT/pools_coaching_frames"   "pools_coaching_frames"
sync_dir "$PROJECT_ROOT/logs"                    "logs"

if [ "$SYNC_ERRORS" -eq 0 ]; then
  log "NAS sync completed successfully"
else
  log "NAS sync completed with $SYNC_ERRORS errors"
fi

# --- Unmount if we mounted it ---
if [ "$ALREADY_MOUNTED" = false ]; then
  sudo umount "$NAS_MOUNT_POINT" 2>/dev/null && log "Unmounted $NAS_MOUNT_POINT" || true
fi

exit "$SYNC_ERRORS"
