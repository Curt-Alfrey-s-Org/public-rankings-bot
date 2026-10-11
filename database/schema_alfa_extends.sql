-- Alfa Rating v2 Schema Extension
-- Adds columns to tournament_history_matches for better context tracking
-- Run: psql -d your_db < database/schema_alfa_extends.sql

-- Extend tournament_history_matches table with Alfa context
ALTER TABLE IF EXISTS tournament_history_matches
ADD COLUMN IF NOT EXISTS table_size VARCHAR(32),  -- "7ft", "8ft", "9ft"
ADD COLUMN IF NOT EXISTS game_format VARCHAR(32) DEFAULT '9ball',  -- "8ball", "9ball", "10ball"
ADD COLUMN IF NOT EXISTS race_to INTEGER,  -- Explicit race-to (can infer from scores)
ADD COLUMN IF NOT EXISTS equipment_ball VARCHAR(64),  -- "standard", "super", "aramith"
ADD COLUMN IF NOT EXISTS equipment_cloth VARCHAR(64),  -- "simonis", "iwan", "other"
ADD COLUMN IF NOT EXISTS event_context VARCHAR(64),  -- "league", "tournament", "casual"
ADD COLUMN IF NOT EXISTS location_city VARCHAR(128),
ADD COLUMN IF NOT EXISTS location_state VARCHAR(128),
ADD COLUMN IF NOT EXISTS location_country VARCHAR(128),
ADD COLUMN IF NOT EXISTS operator_elo_start DOUBLE PRECISION,  -- Alfa rating at match start
ADD COLUMN IF NOT EXISTS player2_elo_start DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS operator_elo_end DOUBLE PRECISION,    -- Alfa rating after match
ADD COLUMN IF NOT EXISTS player2_elo_end DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS match_confidence DOUBLE PRECISION DEFAULT 1.0,  -- 0-1, confidence in this match's validity
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Create index for Alfa queries
CREATE INDEX IF NOT EXISTS idx_thm_table_size ON tournament_history_matches(table_size);
CREATE INDEX IF NOT EXISTS idx_thm_format ON tournament_history_matches(game_format);
CREATE INDEX IF NOT EXISTS idx_thm_event_context ON tournament_history_matches(event_context);
CREATE INDEX IF NOT EXISTS idx_thm_elo_tracking ON tournament_history_matches(operator_elo_start, player2_elo_start);

-- Create a new table for Alfa rating snapshots (tracking rating changes over time)
CREATE TABLE IF NOT EXISTS alfa_player_ratings (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(255) NOT NULL,
    player_name VARCHAR(255) NOT NULL,
    rating DOUBLE PRECISION NOT NULL,
    robustness INTEGER DEFAULT 0,  -- Number of games
    starter_rating DOUBLE PRECISION,
    rating_confidence DOUBLE PRECISION DEFAULT 0.5,  -- 0-1, based on robustness and data quality
    anomaly_score DOUBLE PRECISION DEFAULT 0.0,  -- 0-1, 0=clean, >0.7=suspicious
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_alfa_ratings_player ON alfa_player_ratings(player_id);
CREATE INDEX IF NOT EXISTS idx_alfa_ratings_name ON alfa_player_ratings(player_name);
CREATE INDEX IF NOT EXISTS idx_alfa_ratings_timestamp ON alfa_player_ratings(updated_at DESC);

-- Table for anomaly flags (suspicious patterns detected)
CREATE TABLE IF NOT EXISTS alfa_anomaly_flags (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(255) NOT NULL,
    player_name VARCHAR(255) NOT NULL,
    flag_type VARCHAR(64) NOT NULL,  -- "winning_weak_only", "rating_mismatch", etc.
    flag_value DOUBLE PRECISION,  -- Metrics associated with flag (e.g., 0.85 for 85% weak wins)
    severity VARCHAR(32) DEFAULT 'medium',  -- "low", "medium", "high"
    description TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    manual_review BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_anomaly_player ON alfa_anomaly_flags(player_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_type ON alfa_anomaly_flags(flag_type);
CREATE INDEX IF NOT EXISTS idx_anomaly_severity ON alfa_anomaly_flags(severity);

-- Table for match outcome predictions (for model validation)
CREATE TABLE IF NOT EXISTS alfa_match_predictions (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(255) NOT NULL UNIQUE,
    operator_id VARCHAR(255) NOT NULL,
    player2_id VARCHAR(255) NOT NULL,
    predicted_win_prob_p1 DOUBLE PRECISION NOT NULL,
    predicted_win_prob_p2 DOUBLE PRECISION NOT NULL,
    predicted_race_length DOUBLE PRECISION,  -- Estimated game length in minutes
    actual_winner_id VARCHAR(255),
    actual_winner_games INTEGER,
    actual_loser_games INTEGER,
    brier_score DOUBLE PRECISION,  -- Calibration metric
    prediction_confidence DOUBLE PRECISION DEFAULT 0.5,  -- Based on robustness and coupling
    model_version VARCHAR(32),  -- "fargo_baseline", "alfa_v1", etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_predictions_match ON alfa_match_predictions(match_id);
CREATE INDEX IF NOT EXISTS idx_predictions_players ON alfa_match_predictions(operator_id, player2_id);
CREATE INDEX IF NOT EXISTS idx_predictions_model ON alfa_match_predictions(model_version);

-- Table for factor contributions (explainability)
CREATE TABLE IF NOT EXISTS alfa_prediction_factors (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(255) NOT NULL REFERENCES alfa_match_predictions(match_id) ON DELETE CASCADE,
    factor_name VARCHAR(128) NOT NULL,  -- "rating_gap", "table_size", "format", etc.
    contribution DOUBLE PRECISION NOT NULL,  -- Impact on win probability
    direction VARCHAR(32),  -- "favors_p1", "favors_p2"
    weight DOUBLE PRECISION,  -- How much this factor matters (0-1)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_factors_match ON alfa_prediction_factors(match_id);

-- Monitor training data quality
CREATE TABLE IF NOT EXISTS alfa_data_quality_report (
    id SERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    total_matches INTEGER,
    matches_with_scores INTEGER,
    matches_with_table_size INTEGER,
    matches_with_format INTEGER,
    matches_with_location INTEGER,
    unique_players INTEGER,
    date_range_start DATE,
    date_range_end DATE,
    data_coverage_percent DOUBLE PRECISION,  -- % of matches with all required fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_quality_report_date ON alfa_data_quality_report(report_date DESC);
