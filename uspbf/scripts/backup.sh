#!/usr/bin/env bash
# Backup USPBF WordPress MySQL database and wp-content tree.
#
# Usage: ./scripts/backup.sh
# Env:   BACKUP_DIR (default: <repo>/backups), RETENTION (default: 14)
# Requires: uspbf_db_1 + uspbf_wordpress_1 running; .env with MYSQL_*.
#
# MySQL manual: https://dev.mysql.com/doc/refman/8.4/en/using-mysqldump.html
# WordPress: https://developer.wordpress.org/advanced-administration/security/backup/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
RETENTION="${RETENTION:-14}"
DB_CONTAINER="uspbf_db_1"
WP_CONTAINER="uspbf_wordpress_1"
ENV_FILE="$ROOT/.env"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

_read_env_var() {
  local key="$1"
  local line val
  line="$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$ENV_FILE" 2>/dev/null | head -1 || true)"
  [ -n "$line" ] || return 1
  val="${line#*=}"
  val="${val#"${val%%[![:space:]]*}"}"
  val="${val%"${val##*[![:space:]]}"}"
  val="${val#\"}"; val="${val%\"}"
  val="${val#\'}"; val="${val%\'}"
  printf '%s' "$val"
}

_preflight() {
  command -v docker >/dev/null 2>&1 || die "docker not found in PATH"
  [ -f "$ENV_FILE" ] || die ".env missing — copy env.example to .env first"
  mkdir -p "$BACKUP_DIR"
  [ -w "$BACKUP_DIR" ] || die "backup directory not writable: $BACKUP_DIR"
  docker inspect -f '{{.State.Running}}' "$DB_CONTAINER" 2>/dev/null | grep -qx true \
    || die "container not running: $DB_CONTAINER"
  docker inspect -f '{{.State.Running}}' "$WP_CONTAINER" 2>/dev/null | grep -qx true \
    || die "container not running: $WP_CONTAINER"
}

_apply_retention() {
  local pattern keep="$RETENTION"
  for pattern in "uspbf_db_*.sql.gz" "uspbf_wp-content_*.tar.gz"; do
    mapfile -t old < <(ls -1t "$BACKUP_DIR"/"$pattern" 2>/dev/null || true)
    if ((${#old[@]} > keep)); then
      rm -f "${old[@]:keep}"
    fi
  done
}

cd "$ROOT"
_preflight

MYSQL_DATABASE="$(_read_env_var MYSQL_DATABASE)" || die "MYSQL_DATABASE not set in .env"
MYSQL_USER="$(_read_env_var MYSQL_USER)" || die "MYSQL_USER not set in .env"
MYSQL_PASSWORD="$(_read_env_var MYSQL_PASSWORD)" || die "MYSQL_PASSWORD not set in .env"

TS="$(date +%Y%m%d_%H%M%S)"
SQL_OUT="$BACKUP_DIR/uspbf_db_${TS}.sql.gz"
WP_OUT="$BACKUP_DIR/uspbf_wp-content_${TS}.tar.gz"

# Write to *.partial and rename only on success: a failed dump used to leave a truncated
# uspbf_db_*.sql.gz that looked like a good backup and counted toward RETENTION
# (review 2026-09-26).
cleanup_partial() { rm -f "$SQL_OUT.partial" "$WP_OUT.partial"; }
trap cleanup_partial EXIT

echo "Backing up MySQL ($MYSQL_DATABASE) from $DB_CONTAINER..."
docker exec "$DB_CONTAINER" mysqldump \
  --single-transaction \
  --user="$MYSQL_USER" \
  --password="$MYSQL_PASSWORD" \
  "$MYSQL_DATABASE" | gzip >"$SQL_OUT.partial"
mv -f "$SQL_OUT.partial" "$SQL_OUT"

echo "Archiving wp-content from $WP_CONTAINER..."
docker exec "$WP_CONTAINER" tar czf - -C /var/www/html wp-content >"$WP_OUT.partial"
mv -f "$WP_OUT.partial" "$WP_OUT"

_apply_retention

echo "Backup complete:"
echo "  $SQL_OUT"
echo "  $WP_OUT"
echo "Retention: keep last $RETENTION of each artifact type in $BACKUP_DIR"
