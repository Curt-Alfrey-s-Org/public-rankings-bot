-- Migration: Add stops_played column to tournament_results table
-- Tracks the number of tournament stops a player had participated in at tournament time
-- Author: AI Assistant
-- Date: 2025-02-19

-- Add stops_played column (optional, populated from rankings snapshot at tournament date)
ALTER TABLE tournament_results 
ADD COLUMN IF NOT EXISTS stops_played INTEGER DEFAULT NULL;

-- Add index for better query performance
CREATE INDEX IF NOT EXISTS idx_tournament_results_stops_played ON tournament_results(stops_played);

-- Add comment documenting the field
COMMENT ON COLUMN tournament_results.stops_played IS 'Number of tournament stops player had participated in at tournament date. Populated from rankings snapshot on tournament date.';
