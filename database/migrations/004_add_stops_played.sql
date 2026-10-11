-- Migration: Add stops_played column to rankings table
-- Tracks the number of tournament stops (competitions) a player has participated in
-- Author: AI Assistant
-- Date: 2025-02-19

-- Add stops_played column (optional, for ranking data from WPBA/WPA PDFs)
ALTER TABLE rankings 
ADD COLUMN IF NOT EXISTS stops_played INTEGER DEFAULT 0;

-- Add index for better query performance
CREATE INDEX IF NOT EXISTS idx_rankings_stops_played ON rankings(stops_played);

-- Add comment documenting the field
COMMENT ON COLUMN rankings.stops_played IS 'Number of tournament stops (competitions) participated in. Populated from WPBA/WPA ranking PDFs.';
