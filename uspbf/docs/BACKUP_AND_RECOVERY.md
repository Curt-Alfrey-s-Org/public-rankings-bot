# USPBF — Backup and recovery

Back up the optional WordPress stack (`uspbf_db_1`, `uspbf_wordpress_1`) before major
changes or on a schedule. The public static marketing site lives in the nginx image
(`nginx-config/site/`); these backups cover the CMS database and uploads only.

## Run a backup

From repo root (containers must be running):

```bash
cd /home/ansible/USPBF
./scripts/backup.sh
```

**Output directory:** `backups/` (gitignored), overridable with `BACKUP_DIR`.

Each run creates:

| Artifact | Contents |
|----------|----------|
| `uspbf_db_YYYYMMDD_HHMMSS.sql.gz` | MySQL logical dump (`mysqldump --single-transaction`) |
| `uspbf_wp-content_YYYYMMDD_HHMMSS.tar.gz` | WordPress `wp-content` (themes, plugins, uploads) |

**Retention:** the script keeps the **14 most recent** files of each type and deletes
older ones. Override with `RETENTION=30 ./scripts/backup.sh`.

Credentials are read from `.env` at runtime (`MYSQL_DATABASE`, `MYSQL_USER`,
`MYSQL_PASSWORD`) — never hardcoded in the script.

## Suggested cron (not installed by this repo)

On `apps`, as the operator user that runs Docker:

```cron
15 3 * * * cd /home/ansible/USPBF && ./scripts/backup.sh >> /var/log/uspbf-backup.log 2>&1
```

Use a **systemd timer** instead if you prefer a single process owner on the host.
Copy completed archives off-host (e.g. hub hub share) per cluster storage policy.

## Restore (disaster recovery)

**Test this once** on a non-production host or after stopping the stack on `apps`.

1. **Stop the stack** (leave tunnel running if desired):

   ```bash
   cd /home/ansible/USPBF
   ./scripts/stop.sh
   ```

2. **Replace volumes** (destructive — only when recovering from total loss):

   ```bash
   sudo docker volume rm uspbf_db_data uspbf_wp_data
   sudo docker volume create uspbf_db_data
   sudo docker volume create uspbf_wp_data
   ```

3. **Start DB + WordPress only** (creates fresh MySQL data dir):

   ```bash
   sudo docker compose up -d db wordpress
   ```

   Wait until `uspbf_db_1` is healthy.

4. **Restore database** (pick your backup file):

   ```bash
   gunzip -c backups/uspbf_db_YYYYMMDD_HHMMSS.sql.gz \
     | sudo docker exec -i uspbf_db_1 mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"
   ```

   Load `MYSQL_*` from `.env` in your shell, or substitute values interactively.

5. **Restore wp-content**:

   ```bash
   sudo docker exec -i uspbf_wordpress_1 tar xzf - -C /var/www/html \
     < backups/uspbf_wp-content_YYYYMMDD_HHMMSS.tar.gz
   ```

6. **Bring the full stack back**:

   ```bash
   ./scripts/start.sh
   ```

7. Verify WordPress admin and uploads; re-run `./scripts/switch-site.sh` if nginx mode
   was changed during recovery.

## References

- [MySQL 8.4 — mysqldump](https://dev.mysql.com/doc/refman/8.4/en/using-mysqldump.html)
- [WordPress — backups](https://developer.wordpress.org/advanced-administration/security/backup/)
