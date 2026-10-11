-- Add missing columns to rankings table for full functionality
-- These columns are referenced in the postgres_manager.py queries

-- Add position column (used for sorting)
ALTER TABLE rankings ADD COLUMN IF NOT EXISTS position INTEGER;

-- Add alfa_rating column  
ALTER TABLE rankings ADD COLUMN IF NOT EXISTS alfa_rating DOUBLE PRECISION;

-- Add source_data column (JSONB for additional ranking data)
ALTER TABLE rankings ADD COLUMN IF NOT EXISTS source_data JSONB DEFAULT '{}'::jsonb;

-- Add fargo_robustness column
ALTER TABLE rankings ADD COLUMN IF NOT EXISTS fargo_robustness INTEGER;

-- Create indexes for the new columns
CREATE INDEX IF NOT EXISTS idx_rankings_position ON rankings(position);
CREATE INDEX IF NOT EXISTS idx_rankings_alfa_rating ON rankings(alfa_rating);
CREATE INDEX IF NOT EXISTS idx_rankings_fargo_robustness ON rankings(fargo_robustness);

-- Add comments
COMMENT ON COLUMN rankings.position IS 'Display position for sorting (may differ from rank)';
COMMENT ON COLUMN rankings.alfa_rating IS 'AI-powered Alfa rating for this player';
COMMENT ON COLUMN rankings.source_data IS 'Additional ranking data stored as JSONB';
COMMENT ON COLUMN rankings.fargo_robustness IS 'Robustness score for Fargo rating confidence';
