-- Migration: Remove Sandbagging Detection Fields
-- Date: 2026-02-17
-- Reason: WPA/WPBA tournaments are professional non-handicapped competition.
-- Variance in performance is normal competitive variance, not sandbagging.

-- ============================================================================
-- Remove sandbagging fields from player_ratings table (NEXUS system)
-- ============================================================================

ALTER TABLE player_ratings 
DROP COLUMN IF EXISTS sandbagger_score;

ALTER TABLE player_ratings 
DROP COLUMN IF EXISTS sandbagger_flags;

DROP INDEX IF EXISTS idx_player_ratings_sandbagger;

-- ============================================================================
-- Remove anomaly detection tables if they exist
-- ============================================================================

-- Drop anomaly flags table
DROP TABLE IF EXISTS alfa_anomaly_flags;

-- Drop anomaly validation table (if exists)
DROP TABLE IF EXISTS anomaly_validation;

-- ============================================================================
-- Update model_predictions table to remove sandbagging flag
-- ============================================================================

ALTER TABLE model_predictions 
DROP COLUMN IF EXISTS is_sandbagging_flagged;

DROP INDEX IF EXISTS idx_predictions_flagged;

-- ============================================================================
-- Update rollout tables to remove sandbagging tracking
-- ============================================================================

-- Note: The rollout_anomalies table anomaly_type column may contain
-- 'sandbagging' values. We'll leave the table structure but document
-- that sandbagging detection is deprecated.

-- Add a comment to document the change
COMMENT ON TABLE rollout_anomalies IS 
'Anomaly tracking table. Note: Sandbagging detection deprecated 2026-02-17. 
For WPA/WPBA: variance is normal competitive performance, not sandbagging.';

-- ============================================================================
-- Clean up any existing sandbagging data
-- ============================================================================

-- Remove sandbagging-specific anomaly records
DELETE FROM rollout_anomalies 
WHERE anomaly_type = 'sandbagging';

-- ============================================================================
-- Verification queries (run after migration)
-- ============================================================================

-- Verify player_ratings columns
-- SELECT column_name, data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'player_ratings' 
-- ORDER BY ordinal_position;

-- Verify no sandbagging indexes remain
-- SELECT indexname 
-- FROM pg_indexes 
-- WHERE indexname LIKE '%sandbag%';
