-- Migration: Add tournament_end_date column for date range support
-- Also updates max_players default from 32 to 80
-- Author: AI Assistant
-- Date: 2025

-- Add tournament_end_date column (optional, for multi-day tournaments)
ALTER TABLE tournaments 
ADD COLUMN IF NOT EXISTS tournament_end_date DATE;

-- Update default max_players from 32 to 80 (if using PostgreSQL)
-- Note: Model enforces default
ALTER TABLE tournaments 
ALTER COLUMN max_players SET DEFAULT 80;

-- Add index for date range queries
CREATE INDEX IF NOT EXISTS idx_tournaments_end_date ON tournaments(tournament_end_date);

-- Add comment documenting the change
COMMENT ON COLUMN tournaments.tournament_end_date IS 'Optional end date for multi-day tournaments. If NULL, tournament is single-day (use tournament_date only).';
