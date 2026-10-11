"""
Database schema for Alfa monitoring tables.

Tables:
- sla_metrics: Hourly, daily, monthly SLA metrics
- sla_breaches: SLA breach events and details
- drift_events: Data drift detections
- model_predictions: Recorded predictions for post-hoc analysis
- anomaly_validation: Sandbagging detection validation
- cold_start_tracking: New player convergence tracking
- health_check_log: Health check results over time
- performance_reports: Generated performance and monitoring reports

Run with: psql -U alfadb -d alfadb -f monitoring_tables.sql
"""

-- SLA Metrics Table: Hourly aggregates
CREATE TABLE IF NOT EXISTS sla_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric_date DATE NOT NULL,
    hour INT NOT NULL,
    availability_percent NUMERIC(5,2),
    latency_p95_ms NUMERIC(7,2),
    latency_p99_ms NUMERIC(7,2),
    accuracy_brier NUMERIC(5,3),
    anomaly_precision NUMERIC(5,3),
    anomaly_recall NUMERIC(5,3),
    aggregation_level VARCHAR(20) NOT NULL,  -- 'hourly', 'daily', 'monthly'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (metric_date, hour, aggregation_level)
);

CREATE INDEX idx_sla_metrics_date ON sla_metrics(metric_date DESC);
CREATE INDEX idx_sla_metrics_timestamp ON sla_metrics(timestamp DESC);

-- SLA Breaches Table: Track breach events
CREATE TABLE IF NOT EXISTS sla_breaches (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric_name VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,  -- 'warning', 'critical'
    value_observed NUMERIC(10,3),
    threshold_warning NUMERIC(10,3),
    threshold_critical NUMERIC(10,3),
    duration_minutes INT,
    resolved BOOLEAN DEFAULT FALSE,
    resolution_time TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sla_breaches_severity ON sla_breaches(severity);
CREATE INDEX idx_sla_breaches_resolved ON sla_breaches(resolved);
CREATE INDEX idx_sla_breaches_timestamp ON sla_breaches(timestamp DESC);

-- Drift Events Table: Data drift detections
CREATE TABLE IF NOT EXISTS drift_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    drift_type VARCHAR(50) NOT NULL,  -- 'input_drift', 'output_drift', 'convergence_drift'
    feature_name VARCHAR(100),
    severity VARCHAR(20) NOT NULL,  -- 'minor', 'moderate', 'severe'
    z_score NUMERIC(6,3),
    observed_value NUMERIC(10,3),
    baseline_mean NUMERIC(10,3),
    baseline_std NUMERIC(10,3),
    percent_change NUMERIC(6,2),
    message TEXT,
    action_taken VARCHAR(50),  -- 'flagged_for_investigation', 'retraining_recommended', etc
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_drift_events_type ON drift_events(drift_type);
CREATE INDEX idx_drift_events_severity ON drift_events(severity);
CREATE INDEX idx_drift_events_timestamp ON drift_events(timestamp DESC);

-- Model Predictions Table: Recorded predictions
CREATE TABLE IF NOT EXISTS model_predictions (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(100) UNIQUE NOT NULL,
    prediction_timestamp TIMESTAMPTZ NOT NULL,
    player_id VARCHAR(100),
    predicted_probability NUMERIC(5,4),
    predicted_class INT,  -- 0 or 1
    actual_outcome INT,  -- 0, 1, or NULL if not yet resolved
    outcome_timestamp TIMESTAMPTZ,
    is_sandbagging_flagged BOOLEAN DEFAULT FALSE,
    flagged_correct BOOLEAN,  -- True if flag was correct, False if false positive
    brier_score NUMERIC(5,4),  -- (predicted - actual)^2
    calibration_bucket INT,  -- 0-9 representing 10% buckets
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_predictions_match ON model_predictions(match_id);
CREATE INDEX idx_predictions_timestamp ON model_predictions(prediction_timestamp DESC);
CREATE INDEX idx_predictions_outcome ON model_predictions(outcome_timestamp DESC);
CREATE INDEX idx_predictions_flagged ON model_predictions(is_sandbagging_flagged);

-- Anomaly Validation Table: Sandbagging detection validation
CREATE TABLE IF NOT EXISTS anomaly_validation (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    num_flagged_predictions INT,
    num_correct_flags INT,
    num_false_positives INT,
    num_ground_truth INT,
    precision NUMERIC(5,4),
    recall NUMERIC(5,4),
    f1_score NUMERIC(5,4),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (date)
);

CREATE INDEX idx_anomaly_validation_date ON anomaly_validation(date DESC);

-- Cold Start Tracking Table: New player convergence
CREATE TABLE IF NOT EXISTS cold_start_tracking (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(100) NOT NULL,
    initial_rating INT NOT NULL,
    games_played INT DEFAULT 0,
    final_rating INT,
    converged_at INT,  -- Game number where convergence occurred
    rating_variance NUMERIC(6,2),  -- Variance over last 5 games
    convergence_threshold INT DEFAULT 30,  -- Rating delta threshold
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cold_start_player ON cold_start_tracking(player_id);
CREATE INDEX idx_cold_start_converged ON cold_start_tracking(converged_at);

-- Health Check Log Table: Track health check results
CREATE TABLE IF NOT EXISTS health_check_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    overall_status VARCHAR(20) NOT NULL,  -- 'healthy', 'degraded', 'unhealthy'
    model_status VARCHAR(20),
    model_latency_ms NUMERIC(8,2),
    database_status VARCHAR(20),
    database_latency_ms NUMERIC(8,2),
    cache_status VARCHAR(20),
    cache_latency_ms NUMERIC(8,2),
    cpu_percent NUMERIC(5,2),
    memory_percent NUMERIC(5,2),
    error_rate_percent NUMERIC(5,2),
    uptime_seconds INT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_health_check_status ON health_check_log(overall_status);
CREATE INDEX idx_health_check_timestamp ON health_check_log(timestamp DESC);

-- Performance Reports Table: Generated reports
CREATE TABLE IF NOT EXISTS performance_reports (
    id SERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    report_type VARCHAR(50) NOT NULL,  -- 'daily', 'weekly', 'monthly'
    report_content TEXT NOT NULL,
    metrics_json JSONB,
    summary TEXT,
    alerts_count INT,
    breach_count INT,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (report_date, report_type)
);

CREATE INDEX idx_performance_reports_date ON performance_reports(report_date DESC);
CREATE INDEX idx_performance_reports_type ON performance_reports(report_type);

-- User Feedback Table: Collect user feedback on predictions
CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(100),
    feedback_type VARCHAR(20) NOT NULL,  -- 'thumbs_up', 'thumbs_down', 'comment'
    comment TEXT,
    rating INT,  -- 1-5 star rating if applicable
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_user_feedback_match ON user_feedback(match_id);
CREATE INDEX idx_user_feedback_type ON user_feedback(feedback_type);
CREATE INDEX idx_user_feedback_timestamp ON user_feedback(created_at DESC);

-- Grant permissions (adjust user as needed)
-- GRANT SELECT, INSERT, UPDATE ON sla_metrics TO alfaapi;
-- GRANT SELECT, INSERT, UPDATE ON sla_breaches TO alfaapi;
-- GRANT SELECT, INSERT ON drift_events TO alfaapi;
-- GRANT SELECT, INSERT, UPDATE ON model_predictions TO alfaapi;
-- GRANT SELECT, INSERT ON anomaly_validation TO alfaapi;
-- GRANT SELECT, INSERT, UPDATE ON cold_start_tracking TO alfaapi;
-- GRANT SELECT, INSERT ON health_check_log TO alfaapi;
-- GRANT SELECT, INSERT ON performance_reports TO alfaapi;
-- GRANT SELECT, INSERT ON user_feedback TO alfaapi;

-- Function to clean up old records (retention: 90 days)
CREATE OR REPLACE FUNCTION cleanup_monitoring_data() RETURNS void AS $$
BEGIN
    DELETE FROM model_predictions WHERE prediction_timestamp < NOW() - INTERVAL '90 days';
    DELETE FROM health_check_log WHERE timestamp < NOW() - INTERVAL '30 days';
    DELETE FROM drift_events WHERE timestamp < NOW() - INTERVAL '60 days';
    DELETE FROM sla_breaches WHERE timestamp < NOW() - INTERVAL '90 days';
    DELETE FROM user_feedback WHERE created_at < NOW() - INTERVAL '180 days';
END;
$$ LANGUAGE plpgsql;

-- Schedule cleanup: Add to cron (pg_cron extension)
-- SELECT cron.schedule('cleanup_monitoring_data', '0 2 * * *', 'SELECT cleanup_monitoring_data()');
