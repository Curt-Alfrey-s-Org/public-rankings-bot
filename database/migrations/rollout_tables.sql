"""
Database migrations for Alfa rating rollout tracking
"""

# Migration: Create rollout_tracking table
# This tracks Alfa vs Fargo predictions during gradual rollout

CREATE TABLE rollout_tracking (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    match_id VARCHAR(256) NOT NULL,
    tournament_id VARCHAR(256) NOT NULL,
    user_id VARCHAR(256),
    
    -- Rating method used
    alfa_enabled BOOLEAN NOT NULL,
    rating_method VARCHAR(32) NOT NULL,  -- 'alfa', 'fargo', or 'both'
    
    -- Match outcome
    outcome_actual VARCHAR(10),  -- 'WIN' or 'LOSS'
    
    -- Predictions
    outcome_predicted_alfa VARCHAR(10),  -- Predicted by Alfa
    outcome_predicted_fargo VARCHAR(10),  -- Predicted by Fargo
    confidence_alfa FLOAT,  -- Confidence 0.0-1.0
    confidence_fargo FLOAT,
    
    -- Accuracy metrics
    brier_alfa FLOAT,  -- Brier score for Alfa
    brier_fargo FLOAT,  -- Brier score for Fargo
    correct_alfa BOOLEAN,  -- Was Alfa prediction correct?
    correct_fargo BOOLEAN,  -- Was Fargo prediction correct?
    
    -- Rating changes
    rating_before_alfa FLOAT,
    rating_after_alfa FLOAT,
    rating_before_fargo FLOAT,
    rating_after_fargo FLOAT,
    
    -- Context
    anomaly_detected BOOLEAN DEFAULT FALSE,
    anomaly_type VARCHAR(64),  -- 'sandbagging', 'skill_burst', etc.
    
    -- Metadata
    rollout_phase INT DEFAULT 0,  -- Rollout phase (0-5)
    tournament_type VARCHAR(64),
    notes TEXT,
    
    -- Indices
    INDEX idx_timestamp (timestamp),
    INDEX idx_tournament_id (tournament_id),
    INDEX idx_match_id (match_id),
    INDEX idx_rating_method (rating_method),
    INDEX idx_rollout_phase (rollout_phase),
    UNIQUE KEY uk_match_id (match_id)
);


-- View: v_rollout_metrics_by_percentage
-- Shows comparison metrics aggregated by rollout percentage
CREATE OR REPLACE VIEW v_rollout_metrics_by_percentage AS
SELECT
    rollout_phase,
    COUNT(*) as matches_total,
    COUNT(DISTINCT tournament_id) as tournaments_completed,
    
    -- Alfa metrics
    AVG(brier_alfa) as avg_brier_alfa,
    STDDEV(brier_alfa) as stddev_brier_alfa,
    SUM(CASE WHEN correct_alfa THEN 1 ELSE 0 END) / COUNT(*) as accuracy_alfa,
    
    -- Fargo metrics
    AVG(brier_fargo) as avg_brier_fargo,
    STDDEV(brier_fargo) as stddev_brier_fargo,
    SUM(CASE WHEN correct_fargo THEN 1 ELSE 0 END) / COUNT(*) as accuracy_fargo,
    
    -- Comparison
    (AVG(brier_fargo) - AVG(brier_alfa)) / AVG(brier_fargo) * 100 as improvement_pct,
    
    -- Anomaly detection
    SUM(CASE WHEN anomaly_detected THEN 1 ELSE 0 END) as anomalies_detected,
    SUM(CASE WHEN anomaly_detected AND anomaly_type = 'sandbagging' THEN 1 ELSE 0 END) as sandbagging_detected,
    
    -- Timestamp range
    MIN(timestamp) as period_start,
    MAX(timestamp) as period_end
FROM rollout_tracking
GROUP BY rollout_phase
ORDER BY rollout_phase;


-- View: v_rollout_metrics_hourly
-- Shows metrics by hour for monitoring dashboards
CREATE OR REPLACE VIEW v_rollout_metrics_hourly AS
SELECT
    DATE_TRUNC('hour', timestamp) as hour,
    COUNT(*) as matches_count,
    COUNT(DISTINCT tournament_id) as tournaments_count,
    
    AVG(brier_alfa) as avg_brier_alfa,
    AVG(brier_fargo) as avg_brier_fargo,
    
    SUM(CASE WHEN correct_alfa THEN 1 ELSE 0 END) / COUNT(*) as accuracy_alfa,
    SUM(CASE WHEN correct_fargo THEN 1 ELSE 0 END) / COUNT(*) as accuracy_fargo,
    
    SUM(CASE WHEN anomaly_detected THEN 1 ELSE 0 END) as anomalies_count,
    COUNT(CASE WHEN outcome_actual IS NULL THEN 1 END) as pending_count
FROM rollout_tracking
GROUP BY DATE_TRUNC('hour', timestamp)
ORDER BY hour DESC;


-- View: v_rollout_anomalies
-- Shows detected anomalies for admin review
CREATE OR REPLACE VIEW v_rollout_anomalies AS
SELECT
    match_id,
    tournament_id,
    timestamp,
    user_id,
    anomaly_type,
    rating_before_alfa,
    rating_after_alfa,
    rating_before_fargo,
    rating_after_fargo,
    outcome_predicted_alfa,
    outcome_actual,
    correct_alfa,
    notes
FROM rollout_tracking
WHERE anomaly_detected = TRUE
ORDER BY timestamp DESC;


-- Stored procedure: sp_calculate_phase_metrics
-- Calculates metrics for a specific rollout phase
DELIMITER //

CREATE PROCEDURE sp_calculate_phase_metrics(
    IN p_phase INT,
    OUT p_avg_brier_alfa FLOAT,
    OUT p_avg_brier_fargo FLOAT,
    OUT p_improvement_pct FLOAT,
    OUT p_matches_total INT,
    OUT p_accuracy_alfa FLOAT,
    OUT p_accuracy_fargo FLOAT
)
BEGIN
    SELECT
        AVG(brier_alfa),
        AVG(brier_fargo),
        (AVG(brier_fargo) - AVG(brier_alfa)) / AVG(brier_fargo) * 100,
        COUNT(*),
        SUM(CASE WHEN correct_alfa THEN 1 ELSE 0 END) / COUNT(*),
        SUM(CASE WHEN correct_fargo THEN 1 ELSE 0 END) / COUNT(*)
    INTO
        p_avg_brier_alfa, p_avg_brier_fargo, p_improvement_pct,
        p_matches_total, p_accuracy_alfa, p_accuracy_fargo
    FROM rollout_tracking
    WHERE rollout_phase = p_phase;
END //

DELIMITER ;
