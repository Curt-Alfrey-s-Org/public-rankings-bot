# Database Backup & Restore System

## Overview

Automated backup system with 2-hour intervals and 30-day retention for the Rankings Bot PostgreSQL database.

## Automated Backups

### Configuration
- **Frequency**: Every 2 hours
- **Retention**: 30 days (older backups automatically deleted)
- **Location**: `Rankings-Bot/backups/`
- **Format**: PostgreSQL custom format (.dump)

### Installation

```bash
cd /home/ansible/rankings-bot
python3 scripts/install_backup_cron.py
```

This installs a cron job that runs: `0 */2 * * *` (every 2 hours)

### Manual Backup

```bash
cd /home/ansible/rankings-bot
./scripts/automated_backup_with_retention.sh
```

## Restore from Backup

### Via API (Admin Only)

1. List available backups:
   ```
   GET /api/backups/list
   ```

2. Initiate restore:
   ```
   POST /api/backups/restore
   {
     "backup_filename": "rankings_20260219_1400.dump",
     "confirm": true
   }
   ```

   Response will include manual restore instructions.

### Manual Restore (Recommended)

```bash
cd /home/ansible/rankings-bot

# List available backups
ls -lh backups/

# Restore from specific backup
./scripts/restore_from_backup.sh backups/rankings_20260219_1400.dump

# Type 'YES' when prompted to confirm

# Restart API
sudo systemctl restart rankings-bot-api
```

### Restore Process

1. **Terminates** all active database connections
2. **Drops** the existing database
3. **Recreates** the database
4. **Restores** all data from the selected backup
5. Requires **manual confirmation** (type 'YES')

⚠️ **WARNING**: Restore will overwrite all current data!

## API Endpoints (Admin Only)

All endpoints require admin authentication.

### List Backups
```
GET /api/backups/list
```
Returns all available backups with size, age, and creation date.

### Create Backup
```
POST /api/backups/create
```
Creates new backup in background.

### Restore Backup
```
POST /api/backups/restore
{
  "backup_filename": "rankings_20260219_1400.dump",
  "confirm": true
}
```
Provides manual restore instructions.

### Download Backup
```
GET /api/backups/download/{filename}
```
Downloads backup file.

### Delete Backup
```
DELETE /api/backups/delete/{filename}
```
Deletes a specific backup file.

## Backup Files

### Naming Convention
`rankings_YYYYMMDD_HHMM.dump`

Example: `rankings_20260219_1400.dump` = February 19, 2026 at 14:00

### Storage Location
```
Rankings-Bot/
  backups/
    rankings_20260219_0000.dump
    rankings_20260219_0200.dump
    rankings_20260219_0400.dump
    ...
```

### Retention Policy
- Backups older than 30 days are automatically deleted
- Typical retention: ~360 backups (12 per day × 30 days)
- Average size: 5-50 MB per backup (depending on data volume)

## Monitoring

### Check Backup Status
```bash
# View recent backups
ls -lht /home/ansible/rankings-bot/backups/ | head -20

# View backup cron log
tail -f /home/ansible/rankings-bot/logs/backup_cron.log

# Check cron job
crontab -l | grep backup
```

### Verify Last Backup
```bash
cd /home/ansible/rankings-bot
ls -lt backups/ | head -1
```

## Troubleshooting

### Cron Not Running
```bash
# Check cron service
sudo systemctl status cron

# Check cron logs
sudo tail -f /var/log/syslog | grep CRON
```

### Backup Script Fails
```bash
# Check logs
cat /home/ansible/rankings-bot/logs/backup_cron.log

# Test manually
cd /home/ansible/rankings-bot
./scripts/automated_backup_with_retention.sh
```

### Restore Fails
- Ensure no applications are connected to the database
- Check PostgreSQL service is running: `sudo systemctl status postgresql`
- Verify backup file exists and is readable
- Check disk space: `df -h`

## Best Practices

1. **Before Major Changes**: Create manual backup
   ```bash
   ./scripts/backup_postgres.sh
   ```

2. **After Restore**: 
   - Restart API service
   - Clear Redis cache if applicable
   - Test critical functionality

3. **Regular Testing**: 
   - Periodically test restore process in development
   - Verify backup integrity

4. **Monitoring**:
   - Set up alerts for backup failures
   - Monitor disk space usage
   - Review backup logs weekly

## Recovery Scenarios

### Data Corruption
1. Stop API: `sudo systemctl stop rankings-bot-api`
2. Choose most recent good backup from `/api/backups/list`
3. Run restore script
4. Verify data integrity
5. Start API: `sudo systemctl start rankings-bot-api`

### Accidental Data Deletion
1. Identify time of deletion
2. Choose backup from before that time
3. Restore backup
4. Restart services

### System Migration
1. Create fresh backup on old system
2. Download backup file
3. Upload to new system
4. Install Rankings Bot on new system
5. Restore backup before first start

## Files Reference

- **Backup Script**: `scripts/backup_postgres.sh`
- **Automated Script**: `scripts/automated_backup_with_retention.sh`
- **Restore Script**: `scripts/restore_from_backup.sh`
- **Cron Installer**: `scripts/install_backup_cron.py`
- **API Routes**: `api/routes/backups.py`
- **Backup Directory**: `backups/`
- **Log Files**: `logs/backup.log`, `logs/backup_cron.log`
