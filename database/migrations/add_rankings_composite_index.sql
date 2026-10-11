-- Performance optimization: Add composite index for common query patterns
-- This speeds up queries that filter by ranking_system and snapshot_date together
-- Which is the most common pattern in Dashboard and Rankings pages

-- Create composite index for (ranking_system, snapshot_date DESC) 
-- This optimizes queries like: WHERE ranking_system = ? AND snapshot_date = (SELECT MAX...)
CREATE INDEX IF NOT EXISTS idx_rankings_system_date 
ON rankings(ranking_system, snapshot_date DESC);

-- Add index on (player_name, ranking_system) for enrichment queries
-- This speeds up player data enrichment which does case-insensitive name matching
CREATE INDEX IF NOT EXISTS idx_rankings_player_system
ON rankings(player_name, ranking_system);

-- Analyze table to update query planner statistics
ANALYZE rankings;
