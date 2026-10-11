-- NEXUS rating system schema
-- Run after schema_postgres.sql. Creates player_ratings and extends ai_coach_analyses.
-- Updated 2026-02-17: Removed sandbagging detection fields (normal variance in pro play)

-- Player NEXUS ratings (μ, σ, robustness, status)
CREATE TABLE IF NOT EXISTS player_ratings (
    id SERIAL PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL UNIQUE,
    nexus_rating DOUBLE PRECISION NOT NULL,
    nexus_uncertainty DOUBLE PRECISION NOT NULL,
    nexus_robustness INTEGER NOT NULL DEFAULT 0,
    nexus_status VARCHAR(32) NOT NULL DEFAULT 'new',
    games_contributing INTEGER NOT NULL DEFAULT 0,
    last_game_date DATE,
    fargo_anchored BOOLEAN DEFAULT FALSE,
    video_prior_used BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_player_ratings_player ON player_ratings(player_name);
CREATE INDEX IF NOT EXISTS idx_player_ratings_rating ON player_ratings(nexus_rating DESC);
CREATE INDEX IF NOT EXISTS idx_player_ratings_status ON player_ratings(nexus_status);

-- AI Coach: composite_visual_skill for NEXUS video prior (0-1 scale)
-- analysis_json stores full structured output; this column enables fast prior lookup
-- Run when ai_coach_analyses exists:
-- ALTER TABLE ai_coach_analyses ADD COLUMN composite_visual_skill DOUBLE PRECISION;
