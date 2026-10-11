#!/bin/bash
# Backup Scrape Data (JSON, PDFs) with 30-day retention
# Complements database backups with raw scrape archives
# Run after rankings refresh or on-demand

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups/scrapes"
DATA_DIR="$PROJECT_DIR/data"
PDFS_DIR="$PROJECT_DIR/pdfs"
LOGS_DIR="$PROJECT_DIR/logs"
RETENTION_DAYS=30

# Ensure directories exist
mkdir -p "$BACKUP_DIR" "$LOGS_DIR"

# Logging
LOG_FILE="$LOGS_DIR/scrape_backup.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

echo "============================================================"
echo "SCRAPE ARCHIVE BACKUP"
echo "============================================================"
echo "Started: $(date)"
echo "Retention: $RETENTION_DAYS days"
echo ""

# Create backup timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="scrapes_$TIMESTAMP"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"

echo "[1/5] Creating backup directory..."
mkdir -p "$BACKUP_PATH"

# Backup tournament rankings JSON
echo "[2/5] Archiving per_tournament_rankings.json..."
if [ -f "$DATA_DIR/per_tournament_rankings.json" ]; then
    cp "$DATA_DIR/per_tournament_rankings.json" "$BACKUP_PATH/"
    SIZE=$(du -h "$BACKUP_PATH/per_tournament_rankings.json" | cut -f1)
    echo "  ✅ Compressed: $SIZE"
else
    echo "  ⚠️  File not found: per_tournament_rankings.json"
fi

# Backup any downloaded PDFs
echo "[3/5] Archiving downloaded PDFs..."
if [ -d "$PDFS_DIR" ] && [ "$(ls -A $PDFS_DIR)" ]; then
    cp -r "$PDFS_DIR"/* "$BACKUP_PATH/" 2>/dev/null || true
    PDF_COUNT=$(find "$BACKUP_PATH" -name "*.pdf" 2>/dev/null | wc -l)
    echo "  ✅ PDFs archived: $PDF_COUNT"
else
    echo "  ℹ️  No PDFs found"
fi

# Create metadata file
echo "[4/5] Creating metadata..."
cat > "$BACKUP_PATH/METADATA.json" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "backup_name": "$BACKUP_NAME",
  "location": "$BACKUP_PATH",
  "files": {
    "per_tournament_rankings.json": "$([ -f "$BACKUP_PATH/per_tournament_rankings.json" ] && echo "included" || echo "missing")",
    "pdfs": "included"
  },
  "retention_days": $RETENTION_DAYS,
  "expire_date": "$(date -u -d "+$RETENTION_DAYS days" +%Y-%m-%d)"
}
EOF
echo "  ✅ Metadata created"

# Compress the entire backup
echo "[5/5] Compressing backup..."
FINAL_BACKUP="$BACKUP_DIR/${BACKUP_NAME}.tar.gz"
if tar -czf "$FINAL_BACKUP" -C "$BACKUP_DIR" "$BACKUP_NAME" 2>/dev/null; then
    SIZE=$(du -h "$FINAL_BACKUP" | cut -f1)
    echo "  ✅ Compressed: $FINAL_BACKUP"
    echo "  Size: $SIZE"
    # Remove uncompressed directory after successful compression
    rm -rf "$BACKUP_PATH"
else
    echo "  ⚠️  Compression failed, keeping uncompressed"
fi

# Clean up old backups
echo ""
echo "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -type f -name "scrapes_*.tar.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -type d -name "scrapes_*" -mtime +$RETENTION_DAYS -exec rm -rf {} + 2>/dev/null || true

# Summary
echo ""
echo "Backup Summary:"
ls -lh "$BACKUP_DIR"/scrapes_*.tar.gz 2>/dev/null | tail -5 | awk '{print "  " $9 " (" $5 ")" }'

echo ""
echo "============================================================"
echo "Completed: $(date)"
echo "============================================================"
