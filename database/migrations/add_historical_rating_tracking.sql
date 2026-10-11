-- Historical Rating Tracking and Accuracy System
-- Adds comprehensive historical tracking for Fargo, ALFA, and EST ratings
-- Includes accuracy calculation and self-calibration capabilities

-- ==========================================
-- 1. HISTORICAL RATING ARCHIVE TABLES
-- ==========================================

-- Fargo Rating History Archive
CREATE TABLE IF NOT EXISTS fargo_rating_history (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(255) NOT NULL,
    player_name VARCHAR(255) NOT NULL,
    ranking_system VARCHAR(32),
    old_fargo_rating DOUBLE PRECISION,
    new_fargo_rating DOUBLE PRECISION NOT NULL,
    fargo_source VARCHAR(64), -- 'api', 'scraper', 'manual', etc.
    snapshot_date DATE NOT NULL,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archive_reason VARCHAR(64) DEFAULT 'update',
    confidence_score DOUBLE PRECISION DEFAULT 0.8, -- How confident we are in this rating
    data_quality VARCHAR(32) DEFAULT 'verified' -- 'verified', 'estimated', 'inferred'
);

-- ALFA Rating History Archive
CREATE TABLE IF NOT EXISTS alfa_rating_history (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(255) NOT NULL,
    player_name VARCHAR(255) NOT NULL,
    ranking_system VARCHAR(32),
    old_alfa_rating DOUBLE PRECISION,
    new_alfa_rating DOUBLE PRECISION NOT NULL,
    alfa_model_version VARCHAR(32), -- Which AI model/version calculated this
    snapshot_date DATE NOT NULL,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archive_reason VARCHAR(64) DEFAULT 'update',
    confidence_score DOUBLE PRECISION DEFAULT 0.7,
    prediction_uncertainty DOUBLE PRECISION -- AI model's uncertainty score
);

-- Extend existing EST rating transitions table with additional fields
ALTER TABLE est_rating_transitions
ADD COLUMN IF NOT EXISTS confidence_score DOUBLE PRECISION DEFAULT 0.8,
ADD COLUMN IF NOT EXISTS rating_accuracy DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS opponent_rating_confidence DOUBLE PRECISION;

-- ==========================================
-- 2. RATING ACCURACY TRACKING TABLES
-- ==========================================

-- Overall system accuracy metrics
CREATE TABLE IF NOT EXISTS rating_accuracy_metrics (
    id SERIAL PRIMARY KEY,
    rating_type VARCHAR(32) NOT NULL, -- 'fargo', 'alfa', 'est'
    calculation_date DATE NOT NULL,
    total_predictions INTEGER DEFAULT 0,
    accurate_predictions INTEGER DEFAULT 0,
    mean_absolute_error DOUBLE PRECISION,
    root_mean_squared_error DOUBLE PRECISION,
    accuracy_percentage DOUBLE PRECISION, -- 0.0 to 100.0
    confidence_interval_lower DOUBLE PRECISION,
    confidence_interval_upper DOUBLE PRECISION,
    sample_size INTEGER,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(rating_type, calculation_date)
);

-- Individual player rating accuracy tracking
CREATE TABLE IF NOT EXISTS player_rating_accuracy (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(255) NOT NULL,
    player_name VARCHAR(255) NOT NULL,
    rating_type VARCHAR(32) NOT NULL, -- 'fargo', 'alfa', 'est'
    predicted_rating DOUBLE PRECISION NOT NULL,
    actual_rating DOUBLE PRECISION, -- From FargoRate or verified source
    absolute_error DOUBLE PRECISION,
    accuracy_score DOUBLE PRECISION, -- 0.0 (worst) to 1.0 (perfect)
    confidence_level DOUBLE PRECISION, -- How confident the system is
    prediction_date DATE NOT NULL,
    verification_date DATE,
    data_source VARCHAR(64), -- 'fargorate_api', 'manual_verification', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- 3. SELF-CALIBRATION TABLES
-- ==========================================

-- Rating calibration parameters that evolve over time
CREATE TABLE IF NOT EXISTS rating_calibration_params (
    id SERIAL PRIMARY KEY,
    rating_type VARCHAR(32) NOT NULL,
    parameter_name VARCHAR(64) NOT NULL, -- 'k_factor', 'confidence_base', etc.
    parameter_value DOUBLE PRECISION NOT NULL,
    effective_date DATE NOT NULL,
    calibration_method VARCHAR(64), -- 'fargorate_comparison', 'tournament_validation', etc.
    sample_size INTEGER,
    confidence_interval DOUBLE PRECISION,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(rating_type, parameter_name, effective_date)
);

-- System self-improvement tracking
CREATE TABLE IF NOT EXISTS system_accuracy_improvement (
    id SERIAL PRIMARY KEY,
    improvement_date DATE NOT NULL,
    rating_type VARCHAR(32) NOT NULL,
    previous_accuracy DOUBLE PRECISION,
    new_accuracy DOUBLE PRECISION,
    improvement_amount DOUBLE PRECISION,
    calibration_changes JSONB, -- What parameters were adjusted
    sample_size INTEGER,
    statistical_significance DOUBLE PRECISION,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- 4. INDEXES FOR PERFORMANCE
-- ==========================================

-- Historical rating indexes
CREATE INDEX IF NOT EXISTS idx_fargo_history_player_date ON fargo_rating_history(player_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_fargo_history_player_name ON fargo_rating_history(player_name);
CREATE INDEX IF NOT EXISTS idx_alfa_history_player_date ON alfa_rating_history(player_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_alfa_history_player_name ON alfa_rating_history(player_name);

-- Accuracy tracking indexes
CREATE INDEX IF NOT EXISTS idx_accuracy_metrics_type_date ON rating_accuracy_metrics(rating_type, calculation_date);
CREATE INDEX IF NOT EXISTS idx_player_accuracy_player_type ON player_rating_accuracy(player_id, rating_type);
CREATE INDEX IF NOT EXISTS idx_player_accuracy_date ON player_rating_accuracy(prediction_date);

-- Calibration indexes
CREATE INDEX IF NOT EXISTS idx_calibration_params_type ON rating_calibration_params(rating_type, effective_date);
CREATE INDEX IF NOT EXISTS idx_accuracy_improvement_date ON system_accuracy_improvement(improvement_date);

-- ==========================================
-- 5. FUNCTIONS FOR ACCURACY CALCULATION
-- ==========================================

-- Function to calculate rating accuracy metrics
CREATE OR REPLACE FUNCTION calculate_rating_accuracy(
    p_rating_type VARCHAR(32),
    p_start_date DATE DEFAULT CURRENT_DATE - INTERVAL '30 days',
    p_end_date DATE DEFAULT CURRENT_DATE
) RETURNS TABLE (
    total_predictions BIGINT,
    accurate_predictions BIGINT,
    mean_absolute_error DOUBLE PRECISION,
    accuracy_percentage DOUBLE PRECISION,
    confidence_interval DOUBLE PRECISION
) AS $$
DECLARE
    total_count BIGINT;
    accurate_count BIGINT;
    mae DOUBLE PRECISION;
    accuracy_pct DOUBLE PRECISION;
    conf_interval DOUBLE PRECISION;
BEGIN
    -- Calculate metrics from player_rating_accuracy table
    SELECT
        COUNT(*),
        COUNT(CASE WHEN accuracy_score >= 0.95 THEN 1 END), -- Consider >95% accurate as "accurate"
        AVG(absolute_error),
        AVG(accuracy_score) * 100.0,
        STDDEV(accuracy_score) * 1.96 -- 95% confidence interval
    INTO total_count, accurate_count, mae, accuracy_pct, conf_interval
    FROM player_rating_accuracy
    WHERE rating_type = p_rating_type
      AND prediction_date BETWEEN p_start_date AND p_end_date
      AND actual_rating IS NOT NULL;

    RETURN QUERY SELECT total_count, accurate_count, mae, accuracy_pct, conf_interval;
END;
$$ LANGUAGE plpgsql;

-- Function to archive old ratings before update
CREATE OR REPLACE FUNCTION archive_rating_before_update(
    p_player_id VARCHAR(255),
    p_player_name VARCHAR(255),
    p_rating_type VARCHAR(32),
    p_old_rating DOUBLE PRECISION,
    p_new_rating DOUBLE PRECISION,
    p_ranking_system VARCHAR(32) DEFAULT NULL,
    p_source VARCHAR(64) DEFAULT 'system_update'
) RETURNS VOID AS $$
BEGIN
    IF p_rating_type = 'fargo' THEN
        INSERT INTO fargo_rating_history (
            player_id, player_name, ranking_system,
            old_fargo_rating, new_fargo_rating, fargo_source, snapshot_date
        ) VALUES (
            p_player_id, p_player_name, p_ranking_system,
            p_old_rating, p_new_rating, p_source, CURRENT_DATE
        );
    ELSIF p_rating_type = 'alfa' THEN
        INSERT INTO alfa_rating_history (
            player_id, player_name, ranking_system,
            old_alfa_rating, new_alfa_rating, snapshot_date
        ) VALUES (
            p_player_id, p_player_name, p_ranking_system,
            p_old_rating, p_new_rating, CURRENT_DATE
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ==========================================
-- 6. INITIAL DATA POPULATION
-- ==========================================

-- Populate initial accuracy metrics
INSERT INTO rating_accuracy_metrics (rating_type, calculation_date, total_predictions, accuracy_percentage)
VALUES
    ('fargo', CURRENT_DATE, 0, 85.0), -- Baseline accuracy for Fargo ratings
    ('alfa', CURRENT_DATE, 0, 75.0),  -- Baseline accuracy for ALFA ratings
    ('est', CURRENT_DATE, 0, 80.0)    -- Baseline accuracy for EST ratings
ON CONFLICT (rating_type, calculation_date) DO NOTHING;

-- Initialize calibration parameters with current values
INSERT INTO rating_calibration_params (rating_type, parameter_name, parameter_value, effective_date)
VALUES
    ('est', 'k_factor_base', 32.0, CURRENT_DATE),
    ('est', 'confidence_base', 0.5, CURRENT_DATE),
    ('est', 'confidence_growth_rate', 0.1, CURRENT_DATE),
    ('alfa', 'model_confidence_threshold', 0.7, CURRENT_DATE),
    ('fargo', 'api_reliability_score', 0.9, CURRENT_DATE)
ON CONFLICT (rating_type, parameter_name, effective_date) DO NOTHING;

-- ==========================================
-- 7. VIEWS FOR EASY ACCESS
-- ==========================================

-- View for latest accuracy metrics
CREATE OR REPLACE VIEW v_latest_accuracy_metrics AS
SELECT
    rating_type,
    calculation_date,
    accuracy_percentage,
    total_predictions,
    mean_absolute_error,
    confidence_interval_lower,
    confidence_interval_upper
FROM rating_accuracy_metrics
WHERE (rating_type, calculation_date) IN (
    SELECT rating_type, MAX(calculation_date)
    FROM rating_accuracy_metrics
    GROUP BY rating_type
);

-- View for player rating history (all types combined)
CREATE OR REPLACE VIEW v_player_rating_history AS
-- Fargo history
SELECT
    player_id,
    player_name,
    'fargo' as rating_type,
    new_fargo_rating as rating_value,
    snapshot_date,
    archived_at,
    confidence_score,
    fargo_source as source
FROM fargo_rating_history
UNION ALL
-- ALFA history
SELECT
    player_id,
    player_name,
    'alfa' as rating_type,
    new_alfa_rating as rating_value,
    snapshot_date,
    archived_at,
    confidence_score,
    alfa_model_version as source
FROM alfa_rating_history
UNION ALL
-- EST history (simplified from transitions)
SELECT
    player_id,
    player_name,
    'est' as rating_type,
    new_est_rating as rating_value,
    created_at::date as snapshot_date,
    created_at as archived_at,
    confidence,
    formula_version as source
FROM est_rating_transitions
ORDER BY player_id, snapshot_date;

-- ==========================================
-- 8. COMMENTS AND DOCUMENTATION
-- ==========================================

COMMENT ON TABLE fargo_rating_history IS 'Historical archive of Fargo rating changes for accuracy tracking and self-calibration';
COMMENT ON TABLE alfa_rating_history IS 'Historical archive of ALFA rating changes with AI model versions and uncertainty scores';
COMMENT ON TABLE rating_accuracy_metrics IS 'Overall system accuracy metrics for each rating type over time';
COMMENT ON TABLE player_rating_accuracy IS 'Individual player rating accuracy tracking for detailed analysis';
COMMENT ON TABLE rating_calibration_params IS 'Self-calibration parameters that evolve based on accuracy measurements';
COMMENT ON TABLE system_accuracy_improvement IS 'Tracking of system improvements and calibration changes';

COMMENT ON FUNCTION calculate_rating_accuracy IS 'Calculate comprehensive accuracy metrics for a rating type over a date range';
COMMENT ON FUNCTION archive_rating_before_update IS 'Archive old rating values before updating with new ones';

-- ==========================================
-- 9. PERMISSIONS
-- ==========================================

-- Grant permissions for the application user
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO rankingsbot_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO rankingsbot_user;