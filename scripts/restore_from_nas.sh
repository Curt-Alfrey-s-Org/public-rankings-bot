#!/usr/bin/env bash
# Restore app data from hub SMB share.
# Manual-only: prompts for credentials, mounts, restores, unmounts.
# The app never has standing access to the NAS.
#
# Prerequisites:
#   - cifs-utils installed (sudo apt install cifs-utils)
#   - rsync installed (sudo apt install rsync)
#
# Usage:
#   ./scripts/restore_from_nas.sh                       # Restore ALL directories
#   ./scripts/restore_from_nas.sh backups               # Restore just backups
#   ./scripts/restore_from_nas.sh config                # Restore just config
#   ./scripts/restore_from_nas.sh scraped_data          # Restore just scraped_data
#   ./scripts/restore_from_nas.sh media                 # Restore just media
#   ./scripts/restore_from_nas.sh pools_coaching_frames # Restore just frames
#   ./scripts/restore_from_nas.sh logs                  # Restore just logs
#
# After restoring backups, load the DB dump:
#   ./scripts/restore_from_backup.sh backups/rankings_YYYYMMDD_HHMM.dump

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

NAS_IP="${NAS_IP:-192.0.2.30}"
NAS_SHARE="${NAS_SHARE:-Rankings_app}"
NAS_MOUNT_POINT="${NAS_MOUNT_POINT:-/mnt/hub-backup}"
LOG_FILE="$PROJECT_ROOT/logs/nas_restore.log"

ALL_DIRS=(backups config scraped_data media pools_coaching_frames logs)

log() { echo "[$(date -u '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

mkdir -p "$(dirname "$LOG_FILE")"
sudo mkdir -p "$NAS_MOUNT_POINT"

# Validate argument
RESTORE_TARGET="${1:-all}"
if [ "$RESTORE_TARGET" != "all" ]; then
  VALID=false
  for d in "${ALL_DIRS[@]}"; do
    [ "$d" = "$RESTORE_TARGET" ] && VALID=true
  done
  if [ "$VALID" = false ]; then
    echo "Unknown directory: $RESTORE_TARGET"
    echo "Valid options: ${ALL_DIRS[*]}"
    exit 1
  fi
fi

# --- Mount SMB share ---
ALREADY_MOUNTED=false
if mountpoint -q "$NAS_MOUNT_POINT" 2>/dev/null; then
  ALREADY_MOUNTED=true
  log "NAS already mounted at $NAS_MOUNT_POINT"
else
  MOUNT_OPTS="vers=3.0,uid=$(id -u),gid=$(id -g),file_mode=0664,dir_mode=0775"

  echo ""
  echo "=== Rankings App: hub Restore ==="
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

# --- Show what's on the NAS ---
echo ""
echo "=== NAS contents ==="
if [ "$RESTORE_TARGET" = "all" ]; then
  DIRS_TO_RESTORE=("${ALL_DIRS[@]}")
else
  DIRS_TO_RESTORE=("$RESTORE_TARGET")
fi

HAS_DATA=false
for label in "${DIRS_TO_RESTORE[@]}"; do
  nas_dir="$NAS_MOUNT_POINT/$label"
  if [ -d "$nas_dir" ]; then
    file_count=$(find "$nas_dir" -type f 2>/dev/null | wc -l)
    newest=$(find "$nas_dir" -type f -printf '%T+ %p\n' 2>/dev/null | sort -r | head -1)
    echo "  $label: $file_count files"
    [ -n "$newest" ] && echo "    newest: $newest"
    [ "$file_count" -gt 0 ] && HAS_DATA=true
  else
    echo "  $label: NOT on NAS (nothing to restore)"
  fi
done
echo ""

if [ "$HAS_DATA" = false ]; then
  log "No data found on NAS to restore."
  [ "$ALREADY_MOUNTED" = false ] && sudo umount "$NAS_MOUNT_POINT" 2>/dev/null
  exit 0
fi

# --- Confirm ---
if [ "$RESTORE_TARGET" = "all" ]; then
  echo "This will restore ALL directories from the NAS to the local app."
else
  echo "This will restore '$RESTORE_TARGET' from the NAS to the local app."
fi
echo "Local files that also exist on the NAS will be overwritten."
echo ""
read -rp "Continue? (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  echo "Cancelled."
  [ "$ALREADY_MOUNTED" = false ] && sudo umount "$NAS_MOUNT_POINT" 2>/dev/null
  exit 0
fi

# --- Restore ---
RESTORE_ERRORS=0

restore_dir() {
  local label="$1"
  local nas_dir="$NAS_MOUNT_POINT/$label"
  local local_dir="$PROJECT_ROOT/$label"

  if [ ! -d "$nas_dir" ]; then
    log "  $label: not on NAS, skipping"
    return
  fi

  file_count=$(find "$nas_dir" -type f 2>/dev/null | wc -l)
  if [ "$file_count" -eq 0 ]; then
    log "  $label: empty on NAS, skipping"
    return
  fi

  mkdir -p "$local_dir"
  if rsync --archive --compress --timeout=60 "$nas_dir/" "$local_dir/" 2>>"$LOG_FILE"; then
    log "  $label: restored ($file_count files)"
  else
    log "  $label: FAILED (rsync exit $?)"
    RESTORE_ERRORS=$((RESTORE_ERRORS + 1))
  fi
}

log "NAS restore started <- //${NAS_IP}/${NAS_SHARE}"

for label in "${DIRS_TO_RESTORE[@]}"; do
  restore_dir "$label"
done

if [ "$RESTORE_ERRORS" -eq 0 ]; then
  log "NAS restore completed successfully"
else
  log "NAS restore completed with $RESTORE_ERRORS errors"
fi

# --- Unmount ---
if [ "$ALREADY_MOUNTED" = false ]; then
  sudo umount "$NAS_MOUNT_POINT" 2>/dev/null && log "Unmounted $NAS_MOUNT_POINT" || true
fi

# --- Next steps ---
echo ""
if [ "$RESTORE_TARGET" = "all" ] || [ "$RESTORE_TARGET" = "backups" ]; then
  echo "To restore the database from a backup dump:"
  latest_dump=$(ls -t "$PROJECT_ROOT/backups"/rankings_*.dump 2>/dev/null | head -1)
  if [ -n "$latest_dump" ]; then
    echo "  ./scripts/restore_from_backup.sh $latest_dump"
  else
    echo "  ./scripts/restore_from_backup.sh backups/rankings_YYYYMMDD_HHMM.dump"
  fi
  echo ""
fi

exit "$RESTORE_ERRORS"
