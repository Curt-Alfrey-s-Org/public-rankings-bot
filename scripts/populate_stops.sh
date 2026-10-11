#!/bin/bash
# Populate stops_played and create backups.
# Uses Docker exec for Postgres (no host port). See docs/DOCKER_POSTGRES_ONLY.md.
#
# Usage: ./scripts/populate_stops.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$APP_ROOT/backups}"
CONTAINER="rankings-bot-postgres"

cd "$APP_ROOT"
mkdir -p "$BACKUP_DIR"

DOCKER="${DOCKER:-sudo docker}"

# Load credentials from .env (same pattern as backup_postgres.sh)
if [[ -z "${DATABASE_URL:-}" && -z "${PGHOST:-}" ]] && [[ -f "$APP_ROOT/.env" ]]; then
  val=$(grep -E '^DATABASE_URL\s*=' "$APP_ROOT/.env" 2>/dev/null | sed -E 's/^DATABASE_URL[[:space:]]*=[[:space:]]*//' | tr -d '\r"' | tr -d "'" | head -1) || true
  val="${val%%[[:space:]]*}"
  [[ -n "${val:-}" ]] && export DATABASE_URL="$val"
fi
if [[ -z "$DATABASE_URL" && -z "$PGHOST" ]]; then
  [[ -f "$APP_ROOT/.env" ]] && source "$APP_ROOT/.env" 2>/dev/null || true
  export DATABASE_URL="${DATABASE_URL:-postgresql://rankingsbot_user:${POSTGRES_PASSWORD:-}@rankings-bot-postgres:5432/rankingsbot}"
fi
if [[ -n "$DATABASE_URL" ]] && [[ "$DATABASE_URL" =~ postgresql://([^:]+):([^@]+)@([^:/]+):?([0-9]*)/([^?]+) ]]; then
  PGUSER="${BASH_REMATCH[1]}"
  PGPASSWORD="${BASH_REMATCH[2]}"
  PGDATABASE="${BASH_REMATCH[5]}"
else
  echo "Could not parse DATABASE_URL. Set .env or DATABASE_URL." >&2
  exit 1
fi

if ! $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER}$"; then
  echo "ERROR: Container $CONTAINER not running. Start with: ./scripts/start.sh --deps-only" >&2
  exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
export PGPASSWORD

echo "================================================================================"
echo "POPULATE STOPS_PLAYED - $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================================================"

# Create pre-update backup (docker exec)
echo ""
echo "--- Creating PRE-UPDATE backup ---"
$DOCKER exec "$CONTAINER" pg_dump -U "$PGUSER" -d "$PGDATABASE" -t rankings -F c -f "/tmp/rankings_pre_stops_$TIMESTAMP.sql"
$DOCKER cp "$CONTAINER:/tmp/rankings_pre_stops_$TIMESTAMP.sql" "$BACKUP_DIR/"
$DOCKER exec "$CONTAINER" rm -f "/tmp/rankings_pre_stops_$TIMESTAMP.sql"
echo "✓ Backup: $BACKUP_DIR/rankings_pre_stops_$TIMESTAMP.sql"
ls -lh "$BACKUP_DIR/rankings_pre_stops_$TIMESTAMP.sql"

# Show current state
echo ""
echo "--- Current State ---"
$DOCKER exec -e PGPASSWORD "$CONTAINER" psql -U "$PGUSER" -d "$PGDATABASE" -t -c "
SELECT 
    'Total Players: ' || COUNT(*) || 
    ', With Stops: ' || SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END) ||
    ', Avg: ' || ROUND(AVG(stops_played), 2) as \"Current State\"
FROM rankings;"

# Calculate and update stops
echo ""
echo "--- Calculating Stops from Tournament Data ---"
$DOCKER exec -e PGPASSWORD "$CONTAINER" psql -U "$PGUSER" -d "$PGDATABASE" <<'SQL'
-- Create temp table with stops counts
CREATE TEMP TABLE player_stops AS
SELECT 
    player_name,
    COUNT(DISTINCT tournament_id) as stop_count
FROM tournament_results
GROUP BY player_name;

SELECT 'Found ' || COUNT(*) || ' players in tournaments' as "Tournament Data"
FROM player_stops;

-- Show top 10
SELECT '  ' || ROW_NUMBER() OVER (ORDER BY stop_count DESC) || '. ' ||
       RPAD(player_name, 30) || ' - ' || stop_count || ' tournaments' as "Top Players"
FROM player_stops
ORDER BY stop_count DESC
LIMIT 10;

-- Update rankings table
UPDATE rankings r
SET stops_played = ps.stop_count
FROM player_stops ps
WHERE 
    LOWER(r.player_name) = LOWER(ps.player_name)
    AND r.snapshot_date = (SELECT MAX(snapshot_date) FROM rankings);

SELECT 'Updated ' || COUNT(*) || ' ranking records' as "Update Result"
FROM rankings r
JOIN player_stops ps ON LOWER(r.player_name) = LOWER(ps.player_name)
WHERE r.snapshot_date = (SELECT MAX(snapshot_date) FROM rankings);
SQL

# Show updated state
echo ""
echo "--- Updated State ---"
$DOCKER exec -e PGPASSWORD "$CONTAINER" psql -U "$PGUSER" -d "$PGDATABASE" -t -c "
SELECT 
    'Total Players: ' || COUNT(*) || 
    ', With Stops: ' || SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END) ||
    ', Avg: ' || ROUND(AVG(stops_played), 2) ||
    ', Max: ' || MAX(stops_played) as \"Final State\"
FROM rankings
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM rankings);"
$DOCKER exec -e PGPASSWORD "$CONTAINER" psql -U "$PGUSER" -d "$PGDATABASE" -t -c "
SELECT RPAD(ranking_system, 20) || ' - ' || COUNT(*) || ' players, ' ||
    SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END) || ' with stops, avg: ' || ROUND(AVG(stops_played), 2) as \"By System\"
FROM rankings
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
GROUP BY ranking_system
ORDER BY ranking_system;"

# Create post-update backup
echo ""
echo "--- Creating POST-UPDATE backup ---"
$DOCKER exec "$CONTAINER" pg_dump -U "$PGUSER" -d "$PGDATABASE" -t rankings -F c -f "/tmp/rankings_post_stops_$TIMESTAMP.sql"
$DOCKER cp "$CONTAINER:/tmp/rankings_post_stops_$TIMESTAMP.sql" "$BACKUP_DIR/"
$DOCKER exec "$CONTAINER" rm -f "/tmp/rankings_post_stops_$TIMESTAMP.sql"
echo "✓ Backup: $BACKUP_DIR/rankings_post_stops_$TIMESTAMP.sql"
ls -lh "$BACKUP_DIR/rankings_post_stops_$TIMESTAMP.sql"

# List all backups
echo ""
echo "================================================================================"
echo "ALL BACKUPS"
echo "================================================================================"
ls -lht "$BACKUP_DIR"/rankings_*.sql 2>/dev/null | head -20 || true

echo ""
echo "================================================================================"
echo "✓ STOPS_PLAYED UPDATE COMPLETE"
echo "================================================================================"
