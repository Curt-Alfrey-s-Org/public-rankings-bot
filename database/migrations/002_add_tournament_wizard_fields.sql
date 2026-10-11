-- Migration: Add Tournament Wizard and Test Tournament Fields
-- Date: 2026-02-15
-- Description: Adds support for wizard-based tournament setup and test tournaments visible only to super_admin

-- Add test tournament flag for testing/troubleshooting (super_admin only)
ALTER TABLE tournaments 
ADD COLUMN IF NOT EXISTS is_test_tournament BOOLEAN DEFAULT FALSE;

-- Add setup mode field ('manual' or 'wizard')
ALTER TABLE tournaments 
ADD COLUMN IF NOT EXISTS setup_mode VARCHAR(20) DEFAULT 'manual';

-- Add wizard progress tracking (JSONB for step completion status)
ALTER TABLE tournaments 
ADD COLUMN IF NOT EXISTS wizard_progress JSONB DEFAULT '{}';

-- Add created_by_username for better tracking
ALTER TABLE tournaments 
ADD COLUMN IF NOT EXISTS created_by_username VARCHAR(255);

-- Create index for filtering test tournaments
CREATE INDEX IF NOT EXISTS idx_tournaments_is_test ON tournaments(is_test_tournament);

-- Create index for setup mode filtering
CREATE INDEX IF NOT EXISTS idx_tournaments_setup_mode ON tournaments(setup_mode);

-- Comment documentation
COMMENT ON COLUMN tournaments.is_test_tournament IS 'Flag indicating test tournament (visible only to super_admin for testing)';
COMMENT ON COLUMN tournaments.setup_mode IS 'Tournament setup mode: manual or wizard';
COMMENT ON COLUMN tournaments.wizard_progress IS 'JSON object tracking wizard step completion status';
COMMENT ON COLUMN tournaments.created_by_username IS 'Username of tournament creator for audit trail';
