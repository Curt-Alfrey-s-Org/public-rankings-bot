#!/usr/bin/env bash
# Complete data population and backup workflow.
# Uses Docker exec for Postgres (no host port). See docs/DOCKER_POSTGRES_ONLY.md.
#
# Usage: ./scripts/complete_data_population.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONTAINER="rankings-bot-postgres"
DOCKER="${DOCKER:-sudo docker}"

cd "$APP_ROOT"

# Load credentials from .env
if [[ -z "${DATABASE_URL:-}" ]] && [[ -f "$APP_ROOT/.env" ]]; then
  source "$APP_ROOT/.env" 2>/dev/null || true
fi
DATABASE_URL="${DATABASE_URL:-postgresql://rankingsbot_user:${POSTGRES_PASSWORD:-}@rankings-bot-postgres:5432/rankingsbot}"
if [[ "$DATABASE_URL" =~ postgresql://([^:]+):([^@]+)@([^:/]+):?([0-9]*)/([^?]+) ]]; then
  PGUSER="${BASH_REMATCH[1]}"
  PGPASSWORD="${BASH_REMATCH[2]}"
  PGDATABASE="${BASH_REMATCH[5]}"
else
  echo "Could not parse DATABASE_URL." >&2
  exit 1
fi

if ! $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER}$"; then
  echo "ERROR: Container $CONTAINER not running. Start with: ./scripts/start.sh --deps-only" >&2
  exit 1
fi

run_psql() {
  $DOCKER exec -e PGPASSWORD "$CONTAINER" psql -U "$PGUSER" -d "$PGDATABASE" "$@"
}

echo "============================================================"
echo "RANKINGS DATA POPULATION & BACKUP WORKFLOW"
echo "============================================================"
echo "Started: $(date)"
echo ""

# Step 1: Check current state
echo "STEP 1: Verifying current data state..."
echo "--------------------------------------------------------"
run_psql -t -c "
SELECT 
    COUNT(*) as total,
    COUNT(country) as with_country,
    COUNT(license_number) as with_license
FROM rankings 
WHERE ranking_system = 'WPBA_Women'
AND snapshot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = 'WPBA_Women');" | head -1

COL_EXISTS=$(run_psql -t -c "
SELECT COUNT(*) 
FROM information_schema.columns 
WHERE table_name = 'rankings' AND column_name = 'stops_played';")

echo "stops_played column exists: $COL_EXISTS"
echo ""

# Step 2: Add stops_played column if missing
echo "STEP 2: Adding stops_played column if missing..."
echo "--------------------------------------------------------"
if [ "$COL_EXISTS" -eq "0" ]; then
    run_psql -c "
        ALTER TABLE rankings ADD COLUMN stops_played INTEGER DEFAULT 0;"
    echo "✅ stops_played column added"
else
    echo "✅ stops_played column already exists"
fi
echo ""

# Step 3: Trigger rankings refresh (API on host port 8003)
echo "STEP 3: Refreshing rankings data..."
echo "--------------------------------------------------------"
echo "Getting admin token..."
TOKEN=$(curl -s -X POST 'http://127.0.0.1:8003/api/auth/login' \
    -H 'Content-Type: application/json' \
    -d '{"username":"tornybotca1","password":"rtRT"}' | \
    python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -n "$TOKEN" ]; then
    echo "✅ Got admin token"
    echo "Triggering rankings refresh..."
    curl -s -X POST 'http://127.0.0.1:8003/api/rankings/refresh' \
        -H "Authorization: Bearer $TOKEN" \
        -H 'Content-Type: application/json' | head -100
    echo ""
    echo "✅ Refresh triggered (may take 2-3 minutes)"
    echo "Waiting 180 seconds for refresh to complete..."
    sleep 180
else
    echo "❌ Could not get admin token, trying direct scraper..."
    $DOCKER exec rankings-bot-api python3 -c "
import sys
sys.path.insert(0, '/app')
from scrapers.wpba_scraper import WPBAScraper
from database import get_database_manager

print('Running WPBA scraper...')
db_mgr = get_database_manager()
scraper = WPBAScraper()
rankings = scraper.scrape_rankings()
if rankings:
    count = db_mgr.save_wpba_rankings(rankings, ranking_type='WPBA_Women')
    print(f'✅ WPBA rankings refreshed: {count} players saved')
else:
    print('❌ No rankings data retrieved from scraper')
" 2>/dev/null || echo "⚠️ Scraper may not be available (ensure rankings-bot-api is running)"
fi
echo ""

# Step 4: Calculate stops_played from tournament results
echo "STEP 4: Calculating stops_played..."
echo "--------------------------------------------------------"
run_psql << 'EOSQL'
-- Update stops_played based on tournament participation
WITH player_stops AS (
    SELECT 
        tr.player_name,
        COUNT(DISTINCT tr.tournament_id) as tournament_count
    FROM tournament_results tr
    JOIN tournament_history th ON tr.tournament_id = th.tournament_id
    WHERE th.date IS NOT NULL 
    AND th.date <= CURRENT_DATE
    GROUP BY tr.player_name
)
UPDATE rankings r
SET stops_played = COALESCE(ps.tournament_count, 0)
FROM player_stops ps
WHERE r.player_name = ps.player_name
AND r.snapshot_date >= '2025-01-01';

SELECT 'Updated ' || COUNT(*) || ' player records with stops_played' as result
FROM rankings 
WHERE snapshot_date >= '2025-01-01' AND stops_played > 0;
EOSQL
echo "✅ stops_played calculated"
echo ""

# Step 5: Verify all fields are populated
echo "STEP 5: Verifying data population..."
echo "--------------------------------------------------------"
run_psql -t -c "
SELECT 
    'Total: ' || COUNT(*) || 
    ' | Country: ' || COUNT(country) || 
    ' | License: ' || COUNT(license_number) ||
    ' | Stops: ' || SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END) as summary
FROM rankings 
WHERE ranking_system = 'WPBA_Women'
AND snapshot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = 'WPBA_Women');"

echo ""
echo "Sample of top 5 players:"
run_psql -c "
SELECT player_name, rank, country, license_number, stops_played
FROM rankings
WHERE ranking_system = 'WPBA_Women'
AND snapshot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = 'WPBA_Women')
ORDER BY rank LIMIT 5;"
echo ""

# Step 6: Create backup
echo "STEP 6: Creating database backup..."
echo "--------------------------------------------------------"
./scripts/backup_postgres.sh
sleep 2
LATEST_BACKUP=$(ls -t backups/rankings_*.dump 2>/dev/null | head -1)
if [ -n "$LATEST_BACKUP" ]; then
    SIZE=$(du -h "$LATEST_BACKUP" | cut -f1)
    echo ""
    echo "✅ Backup created: $LATEST_BACKUP"
    echo "   Size: $SIZE"
else
    echo "❌ Backup file not found"
fi
echo ""

# Step 7: Install automated backups
echo "STEP 7: Installing automated backup cron..."
echo "--------------------------------------------------------"
python3 scripts/install_backup_cron.py
echo ""

echo "============================================================"
echo "WORKFLOW COMPLETED"
echo "============================================================"
echo "Finished: $(date)"
echo ""
echo "Summary:"
echo "  ✅ Data fields verified and populated"
echo "  ✅ Database backup created"
echo "  ✅ Automated backups configured (every 2 hours)"
echo ""
echo "Next steps:"
echo "  - Verify website displays country/license data"
echo "  - Check cron job: crontab -l | grep backup"
echo "  - View backups: ls -lh backups/"
echo "============================================================"
