#!/bin/bash
# List all database backups with timestamps

echo "==================================================================="
echo "DATABASE BACKUPS - $(date '+%Y-%m-%d %H:%M:%S')"
echo "==================================================================="
echo ""

BACKUP_DIR="/home/ansible/rankings-bot/backups"

if [ -d "$BACKUP_DIR" ]; then
    echo "Location: $BACKUP_DIR"
    echo ""
    
    # Count backups
    DUMP_COUNT=$(ls "$BACKUP_DIR"/rankings_*.dump 2>/dev/null | wc -l)
    SQL_COUNT=$(ls "$BACKUP_DIR"/rankings_*.sql 2>/dev/null | wc -l)
    
    echo "Summary:"
    echo "  .dump backups: $DUMP_COUNT"
    echo "  .sql backups: $SQL_COUNT"
    echo "  Total: $((DUMP_COUNT + SQL_COUNT))"
    echo ""
    
    # List dump files (most recent 20)
    if [ $DUMP_COUNT -gt 0 ]; then
        echo "Recent .dump backups (last 20):"
        echo "-------------------------------------------------------------------"
        ls -lh "$BACKUP_DIR"/rankings_*.dump 2>/dev/null | tail -20 | awk '{
            size=$5
            date=$6" "$7" "$8
            name=$9
            gsub(/.*\//, "", name)
            printf "  %-40s %8s  %s\n", name, size, date
        }'
        echo ""
    fi
    
    # List sql files
    if [ $SQL_COUNT -gt 0 ]; then
        echo "SQL backups:"
        echo "-------------------------------------------------------------------"
        ls -lh "$BACKUP_DIR"/rankings_*.sql 2>/dev/null | awk '{
            size=$5
            date=$6" "$7" "$8
            name=$9
            gsub(/.*\//, "", name)
            printf "  %-40s %8s  %s\n", name, size, date
        }'
        echo ""
    fi
    
    # Total size
    TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | awk '{print $1}')
    echo "Total backup directory size: $TOTAL_SIZE"
    
else
    echo "Backup directory not found: $BACKUP_DIR"
fi

echo ""
echo "==================================================================="
echo "Automated backups run every 2 hours (configured in cron)"
echo "==================================================================="
