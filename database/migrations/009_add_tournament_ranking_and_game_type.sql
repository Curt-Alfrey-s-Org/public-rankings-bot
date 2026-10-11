-- Migration: Add ranking_system and game_type to tournaments
-- Date: 2026-03-07
-- Description: Support "who the tournament is for" and game type for Auto Fill and display

ALTER TABLE tournaments
ADD COLUMN IF NOT EXISTS ranking_system VARCHAR(32);

ALTER TABLE tournaments
ADD COLUMN IF NOT EXISTS game_type VARCHAR(64);

COMMENT ON COLUMN tournaments.ranking_system IS 'e.g. WPBA_Women, WPA_Men; used for Auto Fill from rankings';
COMMENT ON COLUMN tournaments.game_type IS 'e.g. 9-ball, 8-ball';
