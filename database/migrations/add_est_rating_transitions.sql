-- Live Est. Rating Transitions Table
-- Phase 2: Live Est. Rating Engine - Track rating changes on every rack completion
-- Run: psql -d your_db < database/migrations/add_est_rating_transitions.sql

CREATE TABLE IF NOT EXISTS est_rating_transitions (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(255) NOT NULL,
    player_name VARCHAR(255) NOT NULL,
    match_id VARCHAR(64) NOT NULL REFERENCES matches(match_id),
    game_id INTEGER NOT NULL REFERENCES games(id),
    previous_est_rating DOUBLE PRECISION,
    new_est_rating DOUBLE PRECISION NOT NULL,
    formula_version VARCHAR(32) NOT NULL DEFAULT 'alfa_v2',
    confidence DOUBLE PRECISION DEFAULT 0.5,  -- 0-1, based on robustness and data quality
    robustness INTEGER DEFAULT 0,  -- Number of games contributing to rating
    rating_change DOUBLE PRECISION,  -- Difference: new - previous
    opponent_id VARCHAR(255),  -- The opponent in this game
    opponent_name VARCHAR(255),
    opponent_rating DOUBLE PRECISION,  -- Opponent's rating at game time
    game_outcome VARCHAR(32) NOT NULL,  -- 'win', 'loss'
    game_context JSONB,  -- Additional game metadata (run_out, break_and_run, innings, etc.)
    tournament_id VARCHAR(32),  -- Reference to tournament
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_est_transitions_player ON est_rating_transitions(player_id);
CREATE INDEX IF NOT EXISTS idx_est_transitions_match ON est_rating_transitions(match_id);
CREATE INDEX IF NOT EXISTS idx_est_transitions_game ON est_rating_transitions(game_id);
CREATE INDEX IF NOT EXISTS idx_est_transitions_timestamp ON est_rating_transitions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_est_transitions_formula ON est_rating_transitions(formula_version);

-- Add est_rating columns to players table for live tracking
ALTER TABLE players
ADD COLUMN IF NOT EXISTS est_rating DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS est_rating_confidence DOUBLE PRECISION DEFAULT 0.5,
ADD COLUMN IF NOT EXISTS est_rating_robustness INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS est_rating_last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS est_rating_formula_version VARCHAR(32) DEFAULT 'alfa_v2';

-- Add est_rating to tournament_players for tournament-specific ratings
ALTER TABLE tournament_players
ADD COLUMN IF NOT EXISTS est_rating_start DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS est_rating_end DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS est_rating_games INTEGER DEFAULT 0;

-- Update existing players with initial est_rating from fargo_rating or alfa_rating
UPDATE players
SET est_rating = COALESCE(fargo_score, 500.0),
    est_rating_confidence = CASE
        WHEN fargo_score IS NOT NULL THEN 0.8
        ELSE 0.3
    END,
    est_rating_robustness = 0,
    est_rating_last_updated = CURRENT_TIMESTAMP
WHERE est_rating IS NULL;

-- Create view for current est_ratings
CREATE OR REPLACE VIEW v_current_est_ratings AS
SELECT
    p.player_id,
    p.first_name || ' ' || p.last_name AS player_name,
    p.est_rating,
    p.est_rating_confidence,
    p.est_rating_robustness,
    p.est_rating_last_updated,
    p.est_rating_formula_version,
    p.fargo_score,
    p.membership_status
FROM players p
WHERE p.membership_status = 'active'
  AND p.est_rating IS NOT NULL
ORDER BY p.est_rating DESC NULLS LAST;