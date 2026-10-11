#!/bin/bash
# Deploy Future Tournaments Recovery to Production
# This script safely deploys the recovered future tournament data to production
#
# Usage: ./scripts/deploy_future_tournaments.sh
#
# Prerequisites:
# - Development environment tested and verified
# - Feature branch merged to main (after PR review)
# - Production database backed up

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Starting Future Tournaments Recovery Deployment"
echo "📋 This will deploy 12 recovered future tournaments to production"

# Verify we're on main branch and up to date
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$CURRENT_BRANCH" != "main" ]]; then
    echo "❌ Must be on main branch. Current branch: $CURRENT_BRANCH"
    exit 1
fi

if [[ -n $(git status --porcelain) ]]; then
    echo "❌ Working directory not clean. Please commit or stash changes."
    exit 1
fi

# Backup production database
echo "💾 Creating production backup before deployment..."
"$SCRIPT_DIR/backup_postgres.sh"

# Deploy the schema changes (upcoming_events table)
echo "📦 Applying database schema updates..."
docker exec rankings-bot-postgres psql -U rankingsbot_user -d rankingsbot -f /docker-entrypoint-initdb.d/01-init.sql

# Apply the est_rating migration
docker cp "$PROJECT_ROOT/database/migrations/add_est_rating_transitions.sql" rankings-bot-postgres:/tmp/
docker exec rankings-bot-postgres psql -U rankingsbot_user -d rankingsbot -f /tmp/add_est_rating_transitions.sql

# Import the recovered future tournament data
echo "📤 Importing recovered future tournament data..."
docker cp "$PROJECT_ROOT/future_tournaments.csv" rankings-bot-postgres:/tmp/
docker cp "$PROJECT_ROOT/future_tournament_results.csv" rankings-bot-postgres:/tmp/

docker exec rankings-bot-postgres psql -U rankingsbot_user -d rankingsbot -c "
-- Create upcoming_events table if it doesn't exist
CREATE TABLE IF NOT EXISTS upcoming_events (
    id SERIAL PRIMARY KEY,
    event_id TEXT,
    name TEXT NOT NULL,
    event_date DATE,
    association TEXT,
    status TEXT DEFAULT 'upcoming',
    dedupe_key TEXT,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(dedupe_key)
);

-- Import the recovered data
COPY upcoming_events (event_id, name, event_date, association, status, dedupe_key) 
FROM '/tmp/future_tournaments.csv' WITH CSV HEADER;

-- Import tournament results (if any)
COPY tournament_results (tournament_id, player_name, placement, points) 
FROM '/tmp/future_tournament_results.csv' WITH CSV HEADER;
"

# Verify the deployment
echo "✅ Verifying deployment..."
RESULT=$(docker exec rankings-bot-postgres psql -U rankingsbot_user -d rankingsbot -c "
SELECT COUNT(*) as future_events FROM upcoming_events WHERE event_date > CURRENT_DATE;
SELECT COUNT(*) as total_results FROM tournament_results tr 
JOIN upcoming_events ue ON tr.tournament_id = ue.event_id;
" 2>/dev/null)

echo "📊 Deployment Results:"
echo "$RESULT"

# Restart services
echo "🔄 Restarting production services..."
sudo systemctl restart rankings-bot-api
sudo systemctl restart rankings-bot-celery-worker

echo "🎉 Future tournaments recovery deployment completed!"
echo "📅 12 future tournaments restored to production"
echo "🏆 1 tournament result restored"

# Test the API
echo "🧪 Testing API endpoints..."
sleep 5
if curl -s "http://localhost:8003/api/tournament-history/upcoming" | grep -q '"count":12'; then
    echo "✅ API test passed - future tournaments accessible"
else
    echo "⚠️ API test inconclusive - manual verification recommended"
fi

echo ""
echo "📋 Next Steps:"
echo "  1. Verify frontend displays future tournaments"
echo "  2. Test tournament registration flows"
echo "  3. Monitor for any data integrity issues"
echo "  4. Consider setting up automated data recovery procedures"
