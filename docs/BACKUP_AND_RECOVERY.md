# Backup and Recovery

## Overview

Local backups run every 2 hours via cron. hub sync is **manual only** -- you run `./scripts/sync_to_nas.sh` when you want to push data to the NAS. The app never has standing access to the NAS.

## What is backed up

| Data | Local path | How | To NAS |
|------|-----------|-----|--------|
| PostgreSQL database | `backups/*.dump` | `pg_dump -Fc` via `backup_postgres.sh` | Yes |
| Admin config JSONs | `config/` | Bind mount (live on host) | Yes |
| Scraped data archives | `scraped_data/` | Bind mount | Yes |
| Uploaded media | `media/` | Bind mount | Yes |
| AI coach frames | `pools_coaching_frames/` | Bind mount | Yes |
| Application logs | `logs/` | Bind mount | Yes |

## What is NOT backed up (and why)

| Data | Reason |
|------|--------|
| Redis | Cache only; rebuilt from DB on restart |
| Prometheus/Grafana volumes | Monitoring data; not critical for recovery |
| Frontend dist | Rebuilt from source on deploy |
| Docker images | Rebuilt from Dockerfile on deploy |

## Automated backup flow

Cron runs `scripts/automated_backup_with_retention.sh` every 2 hours:

1. `pg_dump` to `backups/rankings_YYYYMMDD_HHMM.dump` (custom format)
2. Prune `.dump` files older than 30 days

hub sync is separate and manual (see below).

Install the cron:

```bash
python3 scripts/install_backup_cron.py
```

## NAS setup (hub Scale -- SMB)

### hub side

Already configured:
- IP: `192.0.2.30`
- SMB share path: `The_Biz/BIZ_HDDs/Backups/Rankings_app`
- Requires username and password

### App server side

```bash
sudo apt install cifs-utils rsync
```

### Run sync (manual only -- prompts for credentials)

```bash
./scripts/sync_to_nas.sh
```

The script prompts for your hub username and password, mounts the SMB share, syncs all data, then unmounts. No credentials are stored on disk.

### Verify

```bash
# Run sync and check output
./scripts/sync_to_nas.sh

# Check sync log
cat logs/nas_sync.log
```

## Manual backup

```bash
# Database only
./scripts/backup_postgres.sh

# Full sync to NAS
./scripts/sync_to_nas.sh

# Sync to hub (manual, prompts for credentials)
./scripts/sync_to_nas.sh
```

## Recovery from hub

### Restore everything (full disaster recovery)

```bash
./scripts/restore_from_nas.sh
```

Prompts for hub credentials, shows what's on the NAS, asks for confirmation, restores all 6 directories. Then load the database:

```bash
./scripts/restore_from_backup.sh backups/rankings_YYYYMMDD_HHMM.dump
./scripts/full_deploy.sh --production
```

### Restore a single directory (partial recovery)

```bash
./scripts/restore_from_nas.sh config
./scripts/restore_from_nas.sh scraped_data
./scripts/restore_from_nas.sh media
./scripts/restore_from_nas.sh backups
./scripts/restore_from_nas.sh pools_coaching_frames
./scripts/restore_from_nas.sh logs
```

### Database restore from local backup

```bash
./scripts/restore_from_backup.sh backups/rankings_YYYYMMDD_HHMM.dump
```

### Full disaster recovery steps

1. Fresh server: clone repo, copy `.env`
2. `sudo apt install cifs-utils rsync`
3. `./scripts/restore_from_nas.sh` (restores all data from hub)
4. `./scripts/restore_from_backup.sh backups/rankings_YYYYMMDD_HHMM.dump` (load DB)
5. `./scripts/full_deploy.sh --production`

## Oracle Cloud transition

When moving to Oracle Cloud, set up vpn on both Oracle server and hub. The SMB share becomes accessible over the vpn VPN using the vpn IP instead of `192.0.2.30`. Change `NAS_IP` in the sync script or set it via environment variable. No other code changes needed.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NAS_IP` | `192.0.2.30` | hub server IP |
| `NAS_SHARE` | `Rankings_app` | hub SMB share name |
| `NAS_MOUNT_POINT` | `/mnt/hub-backup` | Local mount point (temporary, unmounted after sync) |

## Log files

| Log | Purpose |
|-----|---------|
| `logs/backup.log` | Postgres backup results |
| `logs/backup_cron.log` | Cron execution log |
| `logs/nas_sync.log` | NAS rsync results |
