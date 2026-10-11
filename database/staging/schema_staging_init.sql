-- Staging Database Schema Initialization
-- Copies production Alfa schema to staging with test data
-- Run after standard schema initialization

-- ============================================================================
-- Copy of Production Alfa Tables (for validation and testing)
-- ============================================================================

-- Players table (basic structure)
CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    nationality VARCHAR(255),
    fargo_rating INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tournament history matches (with Alfa extensions)
CREATE TABLE IF NOT EXISTS tournament_history_matches (
    id SERIAL PRIMARY KEY,
    p1_name VARCHAR(255) NOT NULL,
    p2_name VARCHAR(255) NOT NULL,
    p1_games INTEGER NOT NULL,
    p2_games INTEGER NOT NULL,
    tournament_name VARCHAR(500),
    date_played DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Alfa context columns
    table_size VARCHAR(32),
    game_format VARCHAR(32) DEFAULT '9ball',
    race_to INTEGER,
    equipment_ball VARCHAR(64),
    equipment_cloth VARCHAR(64),
    event_context VARCHAR(64),
    location_city VARCHAR(128),
    location_state VARCHAR(128),
    location_country VARCHAR(128),
    operator_elo_start DOUBLE PRECISION,
    player2_elo_start DOUBLE PRECISION,
    operator_elo_end DOUBLE PRECISION,
    player2_elo_end DOUBLE PRECISION,
    match_confidence DOUBLE PRECISION DEFAULT 1.0
);

CREATE INDEX IF NOT EXISTS idx_matches_players ON tournament_history_matches(p1_name, p2_name);
CREATE INDEX IF NOT EXISTS idx_matches_date ON tournament_history_matches(date_played);
CREATE INDEX IF NOT EXISTS idx_thm_table_size ON tournament_history_matches(table_size);
CREATE INDEX IF NOT EXISTS idx_thm_format ON tournament_history_matches(game_format);
CREATE INDEX IF NOT EXISTS idx_thm_event_context ON tournament_history_matches(event_context);

-- Alfa Ratings table
CREATE TABLE IF NOT EXISTS alfa_player_ratings (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(255) NOT NULL,
    player_name VARCHAR(255) NOT NULL,
    rating DOUBLE PRECISION NOT NULL,
    robustness INTEGER DEFAULT 0,
    starter_rating DOUBLE PRECISION,
    rating_confidence DOUBLE PRECISION DEFAULT 0.5,
    anomaly_score DOUBLE PRECISION DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alfa_ratings_player ON alfa_player_ratings(player_id);
CREATE INDEX IF NOT EXISTS idx_alfa_ratings_name ON alfa_player_ratings(player_name);
CREATE INDEX IF NOT EXISTS idx_alfa_ratings_timestamp ON alfa_player_ratings(updated_at DESC);

-- Anomaly Flags table
CREATE TABLE IF NOT EXISTS alfa_anomaly_flags (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(255) NOT NULL,
    player_name VARCHAR(255) NOT NULL,
    flag_type VARCHAR(64) NOT NULL,
    flag_value DOUBLE PRECISION,
    severity VARCHAR(32) DEFAULT 'medium',
    description TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    manual_review BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_anomaly_player ON alfa_anomaly_flags(player_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_type ON alfa_anomaly_flags(flag_type);
CREATE INDEX IF NOT EXISTS idx_anomaly_severity ON alfa_anomaly_flags(severity);

-- Match Predictions table
CREATE TABLE IF NOT EXISTS alfa_match_predictions (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(255) NOT NULL UNIQUE,
    operator_id VARCHAR(255) NOT NULL,
    player2_id VARCHAR(255) NOT NULL,
    predicted_win_prob_p1 DOUBLE PRECISION NOT NULL,
    predicted_win_prob_p2 DOUBLE PRECISION NOT NULL,
    predicted_race_length DOUBLE PRECISION,
    actual_winner_id VARCHAR(255),
    actual_winner_games INTEGER,
    actual_loser_games INTEGER,
    brier_score DOUBLE PRECISION,
    prediction_confidence DOUBLE PRECISION DEFAULT 0.5,
    model_version VARCHAR(32),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_predictions_match ON alfa_match_predictions(match_id);
CREATE INDEX IF NOT EXISTS idx_predictions_players ON alfa_match_predictions(operator_id, player2_id);
CREATE INDEX IF NOT EXISTS idx_predictions_model ON alfa_match_predictions(model_version);

-- Prediction Factors table (explainability)
CREATE TABLE IF NOT EXISTS alfa_prediction_factors (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(255) NOT NULL REFERENCES alfa_match_predictions(match_id) ON DELETE CASCADE,
    factor_name VARCHAR(128) NOT NULL,
    contribution DOUBLE PRECISION NOT NULL,
    direction VARCHAR(32),
    weight DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_factors_match ON alfa_prediction_factors(match_id);

-- Data Quality Report table
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
    data_coverage_percent DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quality_report_date ON alfa_data_quality_report(report_date DESC);

-- ============================================================================
-- Staging-Specific Views for A/B Testing & Comparison
-- ============================================================================

-- Compare Alfa vs Fargo predictions side-by-side
CREATE OR REPLACE VIEW v_alba_vs_fargo_comparison AS
SELECT 
    amp.match_id,
    amp.operator_id,
    amp.player2_id,
    amp.predicted_win_prob_p1 AS alfa_p1_win_prob,
    amp.predicted_win_prob_p2 AS alfa_p2_win_prob,
    thm.p1_name,
    thm.p2_name,
    thm.p1_games,
    thm.p2_games,
    amp.actual_winner_id,
    CASE WHEN amp.actual_winner_id = amp.operator_id THEN 1 ELSE 0 END AS actual_p1_win,
    amp.brier_score,
    amp.prediction_confidence,
    amp.model_version,
    thm.date_played,
    thm.table_size,
    thm.game_format,
    thm.event_context
FROM alfa_match_predictions amp
LEFT JOIN tournament_history_matches thm 
    ON (thm.p1_name = amp.operator_id OR thm.p2_name = amp.operator_id)
    AND (thm.p1_name = amp.player2_id OR thm.p2_name = amp.player2_id)
WHERE amp.model_version IN ('alfa_v1', 'fargo_baseline')
ORDER BY amp.created_at DESC;

-- Staging metrics summary (for monitoring dashboard)
CREATE OR REPLACE VIEW v_staging_metrics_summary AS
SELECT 
    'Total Predictions' AS metric_name,
    COUNT(*) AS metric_value
FROM alfa_match_predictions
UNION ALL
SELECT 
    'Avg Brier Score',
    AVG(brier_score) :: NUMERIC(10, 4)
FROM alfa_match_predictions
WHERE brier_score IS NOT NULL
UNION ALL
SELECT 
    'Model Accuracy (>0.5 calibrated wins)',
    COUNT(CASE WHEN 
        (predicted_win_prob_p1 > 0.5 AND actual_winner_id = operator_id) OR
        (predicted_win_prob_p1 <= 0.5 AND actual_winner_id = player2_id)
    THEN 1 END) * 100.0 / COUNT(*)
FROM alfa_match_predictions
WHERE actual_winner_id IS NOT NULL
UNION ALL
SELECT 
    'Anomalies Detected',
    COUNT(*)
FROM alfa_anomaly_flags
WHERE resolved_at IS NULL
UNION ALL
SELECT 
    'Unique Players Rated',
    COUNT(DISTINCT player_id)
FROM alfa_player_ratings;

-- ============================================================================
-- Staging Seed Data (100 test players with initial ratings)
-- ============================================================================

INSERT INTO players (name, fargo_rating) VALUES
('Test Player 001', 500),
('Test Player 002', 520),
('Test Player 003', 540),
('Test Player 004', 560),
('Test Player 005', 580),
('Test Player 006', 600),
('Test Player 007', 620),
('Test Player 008', 640),
('Test Player 009', 660),
('Test Player 010', 680),
('Test Player 011', 700),
('Test Player 012', 550),
('Test Player 013', 570),
('Test Player 014', 590),
('Test Player 015', 610),
('Test Player 016', 630),
('Test Player 017', 650),
('Test Player 018', 670),
('Test Player 019', 690),
('Test Player 020', 710),
('Test Player 021', 510),
('Test Player 022', 530),
('Test Player 023', 550),
('Test Player 024', 570),
('Test Player 025', 590),
('Test Player 026', 610),
('Test Player 027', 630),
('Test Player 028', 650),
('Test Player 029', 670),
('Test Player 030', 690),
('Test Player 031', 505),
('Test Player 032', 525),
('Test Player 033', 545),
('Test Player 034', 565),
('Test Player 035', 585),
('Test Player 036', 605),
('Test Player 037', 625),
('Test Player 038', 645),
('Test Player 039', 665),
('Test Player 040', 685),
('Test Player 041', 515),
('Test Player 042', 535),
('Test Player 043', 555),
('Test Player 044', 575),
('Test Player 045', 595),
('Test Player 046', 615),
('Test Player 047', 635),
('Test Player 048', 655),
('Test Player 049', 675),
('Test Player 050', 695),
('Test Player 051', 512),
('Test Player 052', 532),
('Test Player 053', 552),
('Test Player 054', 572),
('Test Player 055', 592),
('Test Player 056', 612),
('Test Player 057', 632),
('Test Player 058', 652),
('Test Player 059', 672),
('Test Player 060', 692),
('Test Player 061', 508),
('Test Player 062', 528),
('Test Player 063', 548),
('Test Player 064', 568),
('Test Player 065', 588),
('Test Player 066', 608),
('Test Player 067', 628),
('Test Player 068', 648),
('Test Player 069', 668),
('Test Player 070', 688),
('Test Player 071', 518),
('Test Player 072', 538),
('Test Player 073', 558),
('Test Player 074', 578),
('Test Player 075', 598),
('Test Player 076', 618),
('Test Player 077', 638),
('Test Player 078', 658),
('Test Player 079', 678),
('Test Player 080', 698),
('Test Player 081', 522),
('Test Player 082', 542),
('Test Player 083', 562),
('Test Player 084', 582),
('Test Player 085', 602),
('Test Player 086', 622),
('Test Player 087', 642),
('Test Player 088', 662),
('Test Player 089', 682),
('Test Player 090', 702),
('Test Player 091', 526),
('Test Player 092', 546),
('Test Player 093', 566),
('Test Player 094', 586),
('Test Player 095', 606),
('Test Player 096', 626),
('Test Player 097', 646),
('Test Player 098', 666),
('Test Player 099', 686),
('Test Player 100', 706)
ON CONFLICT DO NOTHING;

-- Initialize Alfa ratings for test players
INSERT INTO alfa_player_ratings (player_id, player_name, rating, robustness, starter_rating, rating_confidence)
SELECT 
    'test_' || id,
    name,
    fargo_rating::DOUBLE PRECISION,
    0,
    fargo_rating::DOUBLE PRECISION,
    0.5
FROM players
WHERE name LIKE 'Test Player%'
ON CONFLICT DO NOTHING;

-- Initialize staging data quality report
INSERT INTO alfa_data_quality_report (report_date, total_matches, unique_players, data_coverage_percent)
VALUES (CURRENT_DATE, 0, 100, 0.0)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Grants and Permissions
-- ============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO rankings;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO rankings;
