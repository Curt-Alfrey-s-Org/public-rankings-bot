#!/usr/bin/env bash
# Automated Postgres Backup with Retention Management
# Runs backup and cleans up backups older than 30 days
# Designed to run every 2 hours via cron
# Usage: ./scripts/automated_backup_with_retention.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
RETENTION_DAYS=30

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Create backup using existing backup script
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting automated backup..."
"$SCRIPT_DIR/backup_postgres.sh"

# Clean up old backups (keep last 30 days)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "rankings_*.dump" -type f -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

# Count remaining backups
backup_count=$(find "$BACKUP_DIR" -name "rankings_*.dump" -type f | wc -l)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup complete. Total backups in retention: $backup_count"

# Log backup info to file
LOG_FILE="$PROJECT_ROOT/logs/backup.log"
mkdir -p "$(dirname "$LOG_FILE")"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup completed. Retention: $backup_count backups" >> "$LOG_FILE"
