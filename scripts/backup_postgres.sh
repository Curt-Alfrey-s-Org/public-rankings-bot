#!/usr/bin/env bash
# Backup Postgres rankings DB using pg_dump.
# Config (per CODING_STANDARDS: use .env, no hardcoded secrets):
#   - Load PROJECT_ROOT/.env if present and DATABASE_URL/PGHOST unset.
#   - Default: postgresql://...@rankings-bot-postgres:5432/... (Docker-network-only; uses docker exec).
#   - No host port. See docs/DOCKER_POSTGRES_ONLY.md.
# Set BACKUP_DIR (default: ./backups) to override dump location.
# Usage: ./scripts/backup_postgres.sh
# Cron: see scripts/cron_backup_postgres.example

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
mkdir -p "$BACKUP_DIR"

# Read DATABASE_URL from .env without sourcing (avoids executing bad .env lines)
if [[ -z "${DATABASE_URL:-}" && -z "${PGHOST:-}" ]] && [[ -f "$PROJECT_ROOT/.env" ]]; then
  val=$(grep -E '^DATABASE_URL\s*=' "$PROJECT_ROOT/.env" 2>/dev/null | sed -E 's/^DATABASE_URL[[:space:]]*=[[:space:]]*//' | tr -d '\r"' | tr -d "'" | head -1) || true
  val="${val%%[[:space:]]*}"
  [[ -n "${val:-}" ]] && export DATABASE_URL="$val"
fi

# Default: Docker-network-only (rankings-bot-postgres). No host port.
if [[ -z "$DATABASE_URL" && -z "$PGHOST" ]]; then
  [[ -f "$PROJECT_ROOT/.env" ]] && source "$PROJECT_ROOT/.env" 2>/dev/null || true
  export DATABASE_URL="${DATABASE_URL:-postgresql://rankingsbot_user:${POSTGRES_PASSWORD:-}@rankings-bot-postgres:5432/rankingsbot}"
fi

# Prefer explicit vars (safe for special chars in password); else parse DATABASE_URL
if [[ -n "$PGHOST" && -n "$PGUSER" && -n "$PGDATABASE" ]]; then
  PGPORT="${PGPORT:-5432}"
elif [[ -n "$DATABASE_URL" ]]; then
  if [[ "$DATABASE_URL" =~ postgresql://([^:]+):([^@]+)@([^:/]+):?([0-9]*)/([^?]+) ]]; then
    PGUSER="${BASH_REMATCH[1]}"
    PGPASSWORD="${BASH_REMATCH[2]}"
    PGHOST="${BASH_REMATCH[3]}"
    PGPORT="${BASH_REMATCH[4]:-5432}"
    PGDATABASE="${BASH_REMATCH[5]}"
  else
    echo "Could not parse DATABASE_URL (use PGHOST, PGUSER, PGPASSWORD, PGDATABASE for complex URLs)" >&2
    exit 1
  fi
else
  echo "Set DATABASE_URL or PGHOST, PGUSER, PGPASSWORD, PGDATABASE" >&2
  exit 1
fi

# Postgres is Docker-network-only (no host port). Use docker exec when host is postgres/rankings-bot-postgres.
# See docs/DOCKER_POSTGRES_ONLY.md.
CONTAINER="rankings-bot-postgres"
USE_DOCKER_EXEC=false
if [[ "$PGHOST" == "postgres" || "$PGHOST" == "rankings-bot-postgres" ]]; then
  USE_DOCKER_EXEC=true
fi

if [[ "$USE_DOCKER_EXEC" == "true" ]]; then
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER}$"; then
    export PGPASSWORD
    stamp=$(date +%Y%m%d_%H%M)
    out="$BACKUP_DIR/rankings_${stamp}.dump"
    docker exec "$CONTAINER" pg_dump -U "${PGUSER}" -Fc "$PGDATABASE" -f "/tmp/rankings_${stamp}.dump"
    docker cp "$CONTAINER:/tmp/rankings_${stamp}.dump" "$out"
    docker exec "$CONTAINER" rm -f "/tmp/rankings_${stamp}.dump"
    echo "Backed up to $out (via docker exec)"
    exit 0
  else
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) INFO: Postgres container $CONTAINER not running; skipping backup (no error)." >&2
    exit 0
  fi
fi

if ! command -v pg_dump &>/dev/null; then
  echo "pg_dump not found. Install PostgreSQL client: sudo apt install postgresql-client" >&2
  exit 127
fi

# Treat "service down" as a skip (same exit policy as the docker-exec branch above):
# cron runs unconditionally, and a stopped DB during maintenance shouldn't alarm. Real
# pg_dump failures still exit non-zero below.
if ! pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" >/dev/null 2>&1; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) INFO: Postgres at $PGHOST:$PGPORT not ready; skipping backup (no error)." >&2
  exit 0
fi

export PGPASSWORD
stamp=$(date +%Y%m%d_%H%M)
out="$BACKUP_DIR/rankings_${stamp}.dump"
pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -Fc "$PGDATABASE" -f "$out"
echo "Backed up to $out"
