-- Data Validation Rules for Cross-System Enrichment
-- 
-- These rules prevent mixing data from different players

BEGIN;

-- Create validation rules table
CREATE TABLE IF NOT EXISTS data_validation_rules (
    id SERIAL PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL,
    verified_license VARCHAR(255),
    verified_country VARCHAR(10),
    verified_fargo_min FLOAT,
    verified_fargo_max FLOAT,
    notes TEXT,
    verified_by VARCHAR(100),
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_name)
);

-- Create validation log table
CREATE TABLE IF NOT EXISTS validation_conflicts (
    id SERIAL PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL,
    conflict_type VARCHAR(50) NOT NULL, -- 'license', 'country', 'fargo'
    system1 VARCHAR(32),
    value1 TEXT,
    system2 VARCHAR(32),
    value2 TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE,
    resolution_notes TEXT
);

-- Function to detect and log conflicts
CREATE OR REPLACE FUNCTION detect_cross_system_conflicts()
RETURNS TABLE(
    player_name VARCHAR(255),
    conflict_type VARCHAR(50),
    details TEXT
) AS $$
BEGIN
    RETURN QUERY
    -- License conflicts
    SELECT 
        r.player_name::VARCHAR(255),
        'LICENSE'::VARCHAR(50),
        string_agg(DISTINCT r.license_number || ' (' || r.ranking_system || ')', ' vs ')::TEXT
    FROM rankings r
    WHERE r.player_name IN (
        SELECT r2.player_name 
        FROM rankings r2
        GROUP BY r2.player_name 
        HAVING COUNT(DISTINCT r2.ranking_system) > 1
    )
    AND r.license_number IS NOT NULL
    GROUP BY r.player_name
    HAVING COUNT(DISTINCT r.license_number) > 1
    
    UNION ALL
    
    -- Country conflicts  
    SELECT 
        r.player_name::VARCHAR(255),
        'COUNTRY'::VARCHAR(50),
        string_agg(DISTINCT r.country || ' (' || r.ranking_system || ')', ' vs ')::TEXT
    FROM rankings r
    WHERE r.player_name IN (
        SELECT r2.player_name 
        FROM rankings r2
        GROUP BY r2.player_name 
        HAVING COUNT(DISTINCT r2.ranking_system) > 1
    )
    AND r.country IS NOT NULL
    GROUP BY r.player_name
    HAVING COUNT(DISTINCT r.country) > 1
    
    UNION ALL
    
    -- Fargo conflicts (>50 point difference)
    SELECT 
        r.player_name::VARCHAR(255),
        'FARGO_MISMATCH'::VARCHAR(50),
        'Range: ' || MIN(r.fargo_rating)::TEXT || ' - ' || MAX(r.fargo_rating)::TEXT || 
        ' (diff: ' || (MAX(r.fargo_rating) - MIN(r.fargo_rating))::TEXT || ')'
    FROM rankings r
    WHERE r.player_name IN (
        SELECT r2.player_name 
        FROM rankings r2
        GROUP BY r2.player_name 
        HAVING COUNT(DISTINCT r2.ranking_system) > 1
    )
    AND r.fargo_rating IS NOT NULL
    GROUP BY r.player_name
    HAVING (MAX(r.fargo_rating) - MIN(r.fargo_rating)) > 50;
END;
$$ LANGUAGE plpgsql;

-- Function to validate player data before merge
CREATE OR REPLACE FUNCTION is_safe_to_merge(p_player_name VARCHAR(255))
RETURNS BOOLEAN AS $$
DECLARE
    license_count INT;
    country_count INT;
    fargo_diff FLOAT;
    has_validation_rule BOOLEAN;
BEGIN
    -- Check if player has validation rule
    SELECT EXISTS(
        SELECT 1 FROM data_validation_rules WHERE player_name = p_player_name
    ) INTO has_validation_rule;
    
    -- If validation rule exists, use it
    IF has_validation_rule THEN
        RETURN TRUE;
    END IF;
    
    -- Check for license conflicts
    SELECT COUNT(DISTINCT license_number)
    INTO license_count
    FROM rankings
    WHERE player_name = p_player_name
        AND license_number IS NOT NULL;
    
    -- Check for country conflicts
    SELECT COUNT(DISTINCT country)
    INTO country_count
    FROM rankings
    WHERE player_name = p_player_name
        AND country IS NOT NULL;
    
    -- Check for Fargo rating variance
    SELECT MAX(fargo_rating) - MIN(fargo_rating)
    INTO fargo_diff
    FROM rankings
    WHERE player_name = p_player_name
        AND fargo_rating IS NOT NULL;
    
    -- Safe if no conflicts
    RETURN (license_count <= 1 AND country_count <= 1 AND (fargo_diff IS NULL OR fargo_diff <= 50));
END;
$$ LANGUAGE plpgsql;

-- Log current conflicts
INSERT INTO validation_conflicts (player_name, conflict_type, system1, value1, system2, value2)
SELECT 
    'Chris Melling', 
    'COUNTRY',
    'WPA_Men',
    'ENG',
    'WPA_Heyball_Men',
    'FIN'
WHERE NOT EXISTS (
    SELECT 1 FROM validation_conflicts 
    WHERE player_name = 'Chris Melling' AND conflict_type = 'COUNTRY'
);

INSERT INTO validation_conflicts (player_name, conflict_type, system1, value1, system2, value2)
SELECT 
    'Joseph Faul',
    'COUNTRY',
    'WPA_Men',
    'RSA',
    'WPA_Heyball_Men',
    'GBR'
WHERE NOT EXISTS (
    SELECT 1 FROM validation_conflicts 
    WHERE player_name = 'Joseph Faul' AND conflict_type = 'COUNTRY'
);

INSERT INTO validation_conflicts (player_name, conflict_type, system1, value1, system2, value2)
SELECT 
    'Katarzyna Wesolowska',
    'COUNTRY',
    'WPA_Women',
    'SLO',
    'WPA_Heyball_Women',
    'POL'
WHERE NOT EXISTS (
    SELECT 1 FROM validation_conflicts 
    WHERE player_name = 'Katarzyna Wesolowska' AND conflict_type = 'COUNTRY'
);

COMMIT;

\echo '';
\echo '================================================================================';
\echo 'DATA VALIDATION SYSTEM INSTALLED';
\echo '================================================================================';
\echo '';
\echo 'Created:';
\echo '  - data_validation_rules table (for verified player data)';
\echo '  - validation_conflicts table (tracking conflicts)';
\echo '  - detect_cross_system_conflicts() function';
\echo '  - is_safe_to_merge() function';
\echo '';
\echo 'Logged 3 existing conflicts for review.';
\echo '';
\echo 'Usage:';
\echo '  -- Check for conflicts:';
\echo '  SELECT * FROM detect_cross_system_conflicts();';
\echo '';
\echo '  -- Check if player is safe to merge:';
\echo '  SELECT player_name, is_safe_to_merge(player_name) FROM rankings GROUP BY player_name;';
\echo '';
\echo '  -- View unresolved conflicts:';
\echo '  SELECT * FROM validation_conflicts WHERE resolved = FALSE;';
\echo '';
