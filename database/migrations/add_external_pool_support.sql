-- Digital Pool Support Migration
-- Adds Digital Pool ranking systems to the database schema
-- Created: February 27, 2026

-- Add Digital Pool ranking systems to the check constraint
ALTER TABLE rankings DROP CONSTRAINT rankings_ranking_system_check;

ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check CHECK (
    ranking_system::text = ANY (ARRAY[
        'WPBA_Women'::character varying,
        'WPA_Men'::character varying,
        'WPA_Women'::character varying,
        'WPBA'::character varying,
        'WPA'::character varying,
        'WPA_Heyball'::character varying,
        'WPA_Heyball_Men'::character varying,
        'WPA_Heyball_Women'::character varying,
        'WPA_Artistic'::character varying,
        'Digital_Pool_9Ball'::character varying,
        'Digital_Pool_10Ball'::character varying,
        'Digital_Pool_8Ball'::character varying,
        'Digital_Pool_StraitPool'::character varying,
        'Digital_Pool_OnePocket'::character varying,
        'Digital_Pool_BankPool'::character varying,
        'Digital_Pool_Women_9Ball'::character varying,
        'Digital_Pool_Men_9Ball'::character varying,
        'Digital_Pool_Mixed_9Ball'::character varying
    ]::text[])
);

-- Create Digital Pool specific metadata table
CREATE TABLE IF NOT EXISTS digital_pool_metadata (
    id SERIAL PRIMARY KEY,
    ranking_system VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    game_type VARCHAR(50) NOT NULL, -- '9Ball', '10Ball', '8Ball', 'StraitPool', 'OnePocket', 'BankPool'
    gender VARCHAR(20), -- 'Men', 'Women', 'Mixed', or NULL for unisex
    region VARCHAR(50), -- Geographic region if applicable
    is_active BOOLEAN DEFAULT true,
    api_endpoint VARCHAR(255), -- Digital Pool API endpoint if available
    last_scraped TIMESTAMP,
    scrape_frequency_hours INTEGER DEFAULT 24,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for Digital Pool metadata
CREATE INDEX IF NOT EXISTS idx_digital_pool_metadata_system ON digital_pool_metadata(ranking_system);
CREATE INDEX IF NOT EXISTS idx_digital_pool_metadata_active ON digital_pool_metadata(is_active);
CREATE INDEX IF NOT EXISTS idx_digital_pool_metadata_game_type ON digital_pool_metadata(game_type);

-- Insert Digital Pool system metadata
INSERT INTO digital_pool_metadata (ranking_system, display_name, game_type, gender, region) VALUES
('Digital_Pool_9Ball', 'Digital Pool 9-Ball Overall', '9Ball', NULL, 'Global'),
('Digital_Pool_10Ball', 'Digital Pool 10-Ball Overall', '10Ball', NULL, 'Global'),
('Digital_Pool_8Ball', 'Digital Pool 8-Ball Overall', '8Ball', NULL, 'Global'),
('Digital_Pool_StraitPool', 'Digital Pool Straight Pool', 'StraitPool', NULL, 'Global'),
('Digital_Pool_OnePocket', 'Digital Pool One Pocket', 'OnePocket', NULL, 'Global'),
('Digital_Pool_BankPool', 'Digital Pool Bank Pool', 'BankPool', NULL, 'Global'),
('Digital_Pool_Women_9Ball', 'Digital Pool 9-Ball Women', '9Ball', 'Women', 'Global'),
('Digital_Pool_Men_9Ball', 'Digital Pool 9-Ball Men', '9Ball', 'Men', 'Global'),
('Digital_Pool_Mixed_9Ball', 'Digital Pool 9-Ball Mixed', '9Ball', 'Mixed', 'Global')
ON CONFLICT (ranking_system) DO NOTHING;

-- Create Digital Pool player profiles table for additional metadata
CREATE TABLE IF NOT EXISTS digital_pool_player_profiles (
    id SERIAL PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL,
    digital_pool_id VARCHAR(100) UNIQUE, -- Digital Pool's internal player ID
    join_date DATE,
    total_matches INTEGER DEFAULT 0,
    win_rate DECIMAL(5,2), -- Percentage as decimal (0.00-1.00)
    rating_points INTEGER DEFAULT 0,
    skill_level VARCHAR(20), -- 'Beginner', 'Intermediate', 'Advanced', 'Professional'
    country VARCHAR(100),
    state_province VARCHAR(100),
    city VARCHAR(100),
    last_active DATE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_name)
);

-- Create indexes for Digital Pool player profiles
CREATE INDEX IF NOT EXISTS idx_digital_pool_profiles_name ON digital_pool_player_profiles(player_name);
CREATE INDEX IF NOT EXISTS idx_digital_pool_profiles_id ON digital_pool_player_profiles(digital_pool_id);
CREATE INDEX IF NOT EXISTS idx_digital_pool_profiles_active ON digital_pool_player_profiles(is_active);
CREATE INDEX IF NOT EXISTS idx_digital_pool_profiles_country ON digital_pool_player_profiles(country);

-- Create Digital Pool match results table for detailed statistics
CREATE TABLE IF NOT EXISTS digital_pool_match_results (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(100) NOT NULL, -- Digital Pool's match ID
    ranking_system VARCHAR(50) NOT NULL,
    operator_name VARCHAR(255) NOT NULL,
    player2_name VARCHAR(255) NOT NULL,
    operator_score INTEGER NOT NULL,
    player2_score INTEGER NOT NULL,
    winner_name VARCHAR(255) NOT NULL,
    match_date DATE NOT NULL,
    game_type VARCHAR(50) NOT NULL,
    table_size VARCHAR(20), -- '7ft', '8ft', '9ft', etc.
    tournament_name VARCHAR(255),
    tournament_round VARCHAR(50),
    duration_minutes INTEGER,
    operator_rating_change INTEGER DEFAULT 0,
    player2_rating_change INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(match_id, ranking_system)
);

-- Create indexes for Digital Pool match results
CREATE INDEX IF NOT EXISTS idx_digital_pool_matches_date ON digital_pool_match_results(match_date);
CREATE INDEX IF NOT EXISTS idx_digital_pool_matches_players ON digital_pool_match_results(operator_name, player2_name);
CREATE INDEX IF NOT EXISTS idx_digital_pool_matches_system ON digital_pool_match_results(ranking_system);
CREATE INDEX IF NOT EXISTS idx_digital_pool_matches_winner ON digital_pool_match_results(winner_name);

-- Update enrichment engine configuration for Digital Pool cross-system relationships
-- This will be handled in the application code, but we document the expected relationships here

-- Add comments to document Digital Pool integration
COMMENT ON TABLE digital_pool_metadata IS 'Metadata for Digital Pool ranking systems including game types, regions, and API endpoints';
COMMENT ON TABLE digital_pool_player_profiles IS 'Extended player profiles for Digital Pool players with additional metadata not in main rankings';
COMMENT ON TABLE digital_pool_match_results IS 'Detailed match results from Digital Pool for advanced analytics and rating calculations';

-- Create a view for Digital Pool rankings with enriched data
CREATE OR REPLACE VIEW digital_pool_rankings_enriched AS
SELECT
    r.*,
    dp.digital_pool_id,
    dp.skill_level,
    dp.win_rate,
    dp.total_matches,
    dp.country as profile_country,
    dp.state_province,
    dp.city,
    dp.last_active
FROM rankings r
LEFT JOIN digital_pool_player_profiles dp ON r.player_name = dp.player_name
WHERE r.ranking_system LIKE 'Digital_Pool_%'
ORDER BY r.ranking_system, r.rank;

-- Grant appropriate permissions (adjust as needed for your setup)
-- GRANT SELECT ON digital_pool_metadata TO rankings_user;
-- GRANT SELECT, INSERT, UPDATE ON digital_pool_player_profiles TO rankings_user;
-- GRANT SELECT, INSERT ON digital_pool_match_results TO rankings_user;
-- GRANT SELECT ON digital_pool_rankings_enriched TO rankings_user;