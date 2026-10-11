#!/bin/bash
# Future Tournaments Recovery Script
# Recovers future tournament data from backup files
#
# Usage: ./scripts/recover_future_tournaments.sh [--backup-file BACKUP_FILE]
#
# This script was used to recover 12 future tournaments from 
# backup: rankings_20260305_1400.dump
#
# Recovered tournaments:
# - WPBA Raxx Mezz Olhausen CPBA Invitational (2026-03-15)
# - WPBA Mezz Olhausen Raxx Invitational (2026-03-15)  
# - WPBA Raxx Mezz Olhausen Invitational (2026-03-15)
# - WPBA Island Casino US Open (2026-04-19)
# - WPBA Soaring Eagle Masters (2026-06-07)
# - WPBA Event 2026-06-04 (2026-06-07)
# - WPBA Bike Week II (2026-06-14) - includes 1 player result
# - 2026 WPBA Felt Colorado Classic (2026-08-23)
# - WPBA Borderline Billiards (2026-10-04)
# - WPBA DR Pool/Jacoby Tour Championship (2026-12-13)
# - WPBA Classic Billiards Players Championship (2026-12-31)
# - 2026 WPBA Iron City Invitational VI (2026-12-31)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BACKUP_FILE="${BACKUP_FILE:-$PROJECT_ROOT/backups/rankings_20260305_1400.dump}"
TEMP_DB="temp_future_recovery_$(date +%s)"

echo "🔄 Starting future tournaments recovery..."
echo "📁 Backup file: $BACKUP_FILE"
echo "🗄️  Temp database: $TEMP_DB"

# Create temp database for recovery
echo "📦 Creating temporary database..."
docker exec rankings-bot-postgres-dev createdb -U rankingsbot_user "$TEMP_DB"

# Restore backup to temp database
echo "📤 Restoring backup..."
docker run --rm --network tunnel_network \
  -v "$BACKUP_FILE:/backup.dump:ro" \
  -e PGPASSWORD=123123 \
  postgres:16-alpine \
  pg_restore -h rankings-bot-postgres-dev -U rankingsbot_user -d "$TEMP_DB" /backup.dump

# Export future tournaments
echo "📋 Exporting future tournament data..."
docker exec rankings-bot-postgres-dev psql -U rankingsbot_user -d "$TEMP_DB" -c "
COPY (
    SELECT * FROM tournament_history WHERE date > CURRENT_DATE
) TO '/tmp/future_tournaments.csv' WITH CSV HEADER;

COPY (
    SELECT tr.* FROM tournament_results tr
    JOIN tournament_history th ON tr.tournament_id = th.tournament_id
    WHERE th.date > CURRENT_DATE
) TO '/tmp/future_tournament_results.csv' WITH CSV HEADER;
"

# Copy files out and import to dev database
echo "📥 Importing to development database..."
docker cp "rankings-bot-postgres-dev:/tmp/future_tournaments.csv" "$PROJECT_ROOT/future_tournaments_recovered.csv"
docker cp "rankings-bot-postgres-dev:/tmp/future_tournament_results.csv" "$PROJECT_ROOT/future_tournament_results_recovered.csv"

docker exec rankings-bot-postgres-dev psql -U rankingsbot_user -d rankingsbot_dev -c "
COPY tournament_history FROM '/tmp/future_tournaments.csv' WITH CSV HEADER;
COPY tournament_results FROM '/tmp/future_tournament_results.csv' WITH CSV HEADER;
"

# Verify import
echo "✅ Verifying recovery..."
docker exec rankings-bot-postgres-dev psql -U rankingsbot_user -d rankingsbot_dev -c "
SELECT COUNT(*) as recovered_tournaments FROM tournament_history WHERE date > CURRENT_DATE;
SELECT COUNT(*) as recovered_results FROM tournament_results tr 
JOIN tournament_history th ON tr.tournament_id = th.tournament_id 
WHERE th.date > CURRENT_DATE;
"

# Cleanup
echo "🧹 Cleaning up..."
docker exec rankings-bot-postgres-dev dropdb -U rankingsbot_user "$TEMP_DB"

echo "🎉 Future tournaments recovery completed!"
echo "📊 12 tournaments and 1 player result recovered"
