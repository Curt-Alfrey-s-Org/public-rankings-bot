#!/bin/bash
# Flatten rankings-bot repo: move Rankings-Bot/ contents to repo root.
# Handles: untracked files (mv), root-owned dirs (sudo rm), junk paste files.
# Run from: /home/ansible/rankings-bot
#
# Usage: ./Rankings-Bot/scripts/flatten_and_preserve_newest.sh [--dry-run]

set -e
cd "$(dirname "$0")/../.."
REPO_ROOT="$(pwd)"
DRY_RUN=false

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

log() { echo "[$(date -u '+%H:%M:%S')] $*"; }
run() {
  if $DRY_RUN; then
    echo "[DRY-RUN] $*"
  else
    "$@"
  fi
}

# --- Step 1: Backup ---
BACKUP_DIR="/home/ansible/rankings-bot.backup.$(date +%Y%m%d_%H%M)"
log "Step 1: Creating backup at $BACKUP_DIR"
run cp -a "$REPO_ROOT" "$BACKUP_DIR"
log "Backup done."

# --- Step 2: Verify Rankings-Bot exists ---
if [[ ! -d "$REPO_ROOT/Rankings-Bot" ]]; then
  log "ERROR: Rankings-Bot/ not found. Nothing to flatten."
  exit 1
fi

# --- Step 3: Remove root-level duplicates (older copies) ---
log "Step 3: Removing root-level duplicate dirs..."
for d in api frontend docs scripts database scrapers tests mobile config backend alembic; do
  if [[ -d "$REPO_ROOT/$d" ]] && [[ -d "$REPO_ROOT/Rankings-Bot/$d" ]]; then
    run rm -rf "$REPO_ROOT/$d"
    log "  Removed $d"
  fi
done

# --- Step 4: Remove root-owned dirs in Rankings-Bot (pools_coaching_frames, etc.) ---
log "Step 4: Removing root-owned dirs in Rankings-Bot (requires sudo)..."
for d in pools_coaching_frames; do
  if [[ -d "$REPO_ROOT/Rankings-Bot/$d" ]]; then
    run sudo rm -rf "$REPO_ROOT/Rankings-Bot/$d"
    log "  Removed $d (root-owned)"
  fi
done
# Fix ownership of other root-owned items so we can move them
if [[ -d "$REPO_ROOT/Rankings-Bot/config" ]] && [[ "$(stat -c '%U' "$REPO_ROOT/Rankings-Bot/config" 2>/dev/null)" == "root" ]]; then
  run sudo chown -R ansible:ansible "$REPO_ROOT/Rankings-Bot/config"
fi
if [[ -d "$REPO_ROOT/Rankings-Bot/bot_auth.db" ]] || [[ -f "$REPO_ROOT/Rankings-Bot/bot_auth.db" ]]; then
  run sudo chown -R ansible:ansible "$REPO_ROOT/Rankings-Bot/bot_auth.db" 2>/dev/null || true
fi

# --- Step 5: Delete junk paste files in Rankings-Bot ---
log "Step 5: Removing junk paste files..."
JUNK=(
  "_and_date,) = cur.fetchone()"
  "= cur.fetchall()"
  "= cur.fetchone()[0]"
  "by tournament participation:\""
  "e_number', 'stops_played')"
  "hot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = 'WPBA_Women')"
  "hot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = 'WPBA_Women');"
  "napshot_date = (SELECT MAX(snapshot_date) FROM rankings);"
  "on"
  "on.dumps(double_64_points),"
  "ingle\","
  "tatus"
  "t=localhost"
  "to be PostgreSQL"
  "tory_recent mv"
  "tory th"
  "total_players,"
  "t terminal output\""
  "ubprocess"
  "ubprocess.check_output(cmd, text=True))"
  "udo journalctl -u rankings-bot-api -n 20 --no-pager | grep -i \"login|password\""
  "ult.returncode)"
  "ults"
  ", {with_stops} with stops > 0\""
  "ycopg2"
  "ycopg2.connect(dbname=\"rankings\", user=\"rankings\", password=\"rankings\", host=\"localhost\")"
  "ys"
  "ys.path.insert(0, os.getcwd())"
  "ystemctl cat rankings-bot-api.service"
)
for j in "${JUNK[@]}"; do
  if [[ -e "$REPO_ROOT/Rankings-Bot/$j" ]]; then
    run rm -f "$REPO_ROOT/Rankings-Bot/$j"
    log "  Removed junk: $j"
  fi
done
# Also remove aux | grep... (glob to match)
run rm -f "$REPO_ROOT/Rankings-Bot/aux | grep"* 2>/dev/null || true

# --- Step 6: Move Rankings-Bot contents up ---
log "Step 6: Moving Rankings-Bot contents to repo root..."
cd "$REPO_ROOT"

for item in Rankings-Bot/*; do
  [[ -e "$item" ]] || continue
  name=$(basename "$item")
  [[ "$name" == ".git" ]] && continue
  if [[ -e "$name" ]]; then
    run rm -rf "$name"
  fi
  if git ls-files --error-unmatch "Rankings-Bot/$name" &>/dev/null 2>&1; then
    run git mv "Rankings-Bot/$name" .
  else
    run mv "Rankings-Bot/$name" .
  fi
  log "  Moved $name"
done

for item in Rankings-Bot/.[!.]* Rankings-Bot/..?*; do
  [[ -e "$item" ]] || continue
  name=$(basename "$item")
  [[ "$name" == ".git" ]] && continue
  if [[ -e "$name" ]]; then
    run rm -rf "$name"
  fi
  if git ls-files --error-unmatch "Rankings-Bot/$name" &>/dev/null 2>&1; then
    run git mv "Rankings-Bot/$name" .
  else
    run mv "Rankings-Bot/$name" .
  fi
  log "  Moved $name"
done

# --- Step 7: Remove Rankings-Bot ---
log "Step 7: Removing Rankings-Bot directory..."
if [[ -d "$REPO_ROOT/Rankings-Bot" ]]; then
  remaining=$(ls -A "$REPO_ROOT/Rankings-Bot" 2>/dev/null | wc -l)
  if [[ "$remaining" -gt 0 ]]; then
    log "  WARNING: Rankings-Bot still has $remaining items. Use: sudo rm -rf Rankings-Bot"
    run sudo rm -rf "$REPO_ROOT/Rankings-Bot"
  else
    run rmdir "$REPO_ROOT/Rankings-Bot"
  fi
fi

# --- Step 8: Backup branch ---
log "Step 8: Creating backup branch..."
run git branch backup-before-flatten 2>/dev/null || true

log "Done. Backup at: $BACKUP_DIR"
log "Next: git status, update systemd paths, test, commit, push."
