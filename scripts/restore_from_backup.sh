#!/usr/bin/env bash
# Restore Rankings Database from Backup
# Usage: ./scripts/restore_from_backup.sh [--docker] <backup_file>
# Example: ./scripts/restore_from_backup.sh backups/rankings_20260219_1000.dump
# With Docker (bypasses host connection): ./scripts/restore_from_backup.sh --docker backups/rankings_20260219_1000.dump

set -e

USE_DOCKER=""
if [[ "${1:-}" == "--docker" ]]; then
  USE_DOCKER=1
  shift
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 [--docker] <backup_file.dump>" >&2
  echo "  --docker  Run restore via docker exec (use when host connection fails)" >&2
  echo "Available backups:" >&2
  find "$(dirname "$0")/../backups" -name "rankings_*.dump" -type f -printf "%TY-%Tm-%Td %TH:%TM %p\n" 2>/dev/null | sort -r || true
  exit 1
fi

BACKUP_FILE="$1"
if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Error: Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Read DATABASE_URL from .env
if [[ -z "${DATABASE_URL:-}" ]] && [[ -f "$PROJECT_ROOT/.env" ]]; then
  val=$(grep -E '^DATABASE_URL\s*=' "$PROJECT_ROOT/.env" 2>/dev/null | sed -E 's/^DATABASE_URL[[:space:]]*=[[:space:]]*//' | tr -d '\r"' | tr -d "'" | head -1) || true
  val="${val%%[[:space:]]*}"
  [[ -n "${val:-}" ]] && export DATABASE_URL="$val"
fi

# Default: Docker-network-only. Use --docker. No host port.
if [[ -z "$DATABASE_URL" ]]; then
  [[ -f "$PROJECT_ROOT/.env" ]] && source "$PROJECT_ROOT/.env" 2>/dev/null || true
  export DATABASE_URL="${DATABASE_URL:-postgresql://rankingsbot_user:${POSTGRES_PASSWORD:-}@rankings-bot-postgres:5432/rankingsbot}"
fi

# Parse connection details
if [[ "$DATABASE_URL" =~ postgresql://([^:]+):([^@]+)@([^:/]+):?([0-9]*)/([^?]+) ]]; then
  PGUSER="${BASH_REMATCH[1]}"
  PGPASSWORD="${BASH_REMATCH[2]}"
  PGHOST="${BASH_REMATCH[3]}"
  PGPORT="${BASH_REMATCH[4]:-5432}"
  PGDATABASE="${BASH_REMATCH[5]}"
else
  echo "Could not parse DATABASE_URL" >&2
  exit 1
fi

# Postgres is Docker-network-only (no host port). When DATABASE_URL points at
# postgres/rankings-bot-postgres, use --docker path. Host connection won't work.
if [[ "$PGHOST" == "postgres" || "$PGHOST" == "rankings-bot-postgres" ]]; then
  if [[ -z "$USE_DOCKER" ]]; then
    echo "Postgres is Docker-network-only. Use: $0 --docker $BACKUP_FILE" >&2
    exit 1
  fi
fi

if ! command -v pg_restore &>/dev/null; then
  echo "pg_restore not found. Install PostgreSQL client: sudo apt install postgresql-client" >&2
  exit 127
fi

# Confirm restore
echo "⚠️  WARNING: This will restore the database from: $(basename "$BACKUP_FILE")"
echo "   Database: $PGDATABASE on $PGHOST:$PGPORT"
echo "   This will:"
echo "   1. Terminate all active connections"
echo "   2. Drop and recreate the database"
echo "   3. Restore data from backup"
echo ""
read -p "Are you sure? Type 'YES' to continue: " confirm
if [[ "$confirm" != "YES" ]]; then
  echo "Restore cancelled."
  exit 0
fi

# Docker path: run pg_restore inside postgres container (bypasses host connection/auth)
if [[ -n "$USE_DOCKER" ]]; then
  CONTAINER="rankings-bot-postgres"
  if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER}$"; then
    echo "Error: Container $CONTAINER not running. Start with: docker compose up -d postgres" >&2
    exit 1
  fi
  # Load POSTGRES_* from .env for container credentials
  [[ -f "$PROJECT_ROOT/.env" ]] && set -a && source "$PROJECT_ROOT/.env" 2>/dev/null && set +a
  PGUSER="${POSTGRES_USER:-rankingsbot_user}"
  PGDATABASE="${POSTGRES_DB:-rankingsbot}"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restoring via Docker (container: $CONTAINER)..."
  # Use postgres:16 client for pg_restore (backup may be from pg_dump 16; format 1.15)
  # Connect to rankings-bot-postgres on same network
  PGPASS="${POSTGRES_PASSWORD:-}"
  net=$(docker inspect rankings-bot-postgres --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' 2>/dev/null | head -1)
  net="${net:-tunnel_network}"
  docker run --rm --network "$net" \
    -e PGPASSWORD="$PGPASS" \
    -v "$(realpath "$BACKUP_FILE"):/restore.dump:ro" \
    postgres:16-alpine \
    sh -c "
      psql -h rankings-bot-postgres -p 5432 -U $PGUSER -d postgres -c \"
        SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$PGDATABASE' AND pid <> pg_backend_pid();
      \" 2>/dev/null || true
      psql -h rankings-bot-postgres -p 5432 -U $PGUSER -d postgres -c \"DROP DATABASE IF EXISTS $PGDATABASE;\"
      psql -h rankings-bot-postgres -p 5432 -U $PGUSER -d postgres -c \"CREATE DATABASE $PGDATABASE OWNER $PGUSER;\"
      pg_restore -h rankings-bot-postgres -p 5432 -U $PGUSER -d $PGDATABASE -v --no-owner /restore.dump
    "
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Database restored successfully from: $(basename "$BACKUP_FILE")"
  echo ""
  echo "Next steps:"
  echo "  1. Restart containers: cd $APP_ROOT && ./scripts/full_deploy.sh --force-docker"
  exit 0
fi

export PGPASSWORD

# Quick connectivity check
if ! PGPASSWORD="$PGPASSWORD" psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c "SELECT 1" &>/dev/null; then
  echo "Error: Cannot connect to Postgres at $PGHOST:$PGPORT" >&2
  echo "If using Docker, start Postgres first: docker compose up -d postgres" >&2
  echo "Postgres is Docker-network-only. Use: $0 --docker $BACKUP_FILE" >&2
  exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Terminating active connections..."
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c "
  SELECT pg_terminate_backend(pid) 
  FROM pg_stat_activity 
  WHERE datname = '$PGDATABASE' AND pid <> pg_backend_pid();
" 2>/dev/null || true

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Dropping database..."
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c "DROP DATABASE IF EXISTS $PGDATABASE;"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Creating database..."
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c "CREATE DATABASE $PGDATABASE OWNER $PGUSER;"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restoring from backup..."
pg_restore -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -v "$BACKUP_FILE"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Database restored successfully from: $(basename "$BACKUP_FILE")"
echo ""
echo "Next steps:"
echo "  1. Restart containers: cd $APP_ROOT && ./scripts/full_deploy.sh --force-docker"
echo "  2. Check the application"
