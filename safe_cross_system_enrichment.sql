-- SAFE Cross-System Data Enrichment with Conflict Detection
-- 
-- Only merges data when there are NO conflicts between systems.
-- Reports any conflicts for manual review.

BEGIN;

-- Step 1: Find players in multiple systems
CREATE TEMP TABLE cross_system_players AS
SELECT DISTINCT player_name
FROM rankings
GROUP BY player_name
HAVING COUNT(DISTINCT ranking_system) > 1;

-- Step 2: Detect conflicts (same player with different non-null values)
CREATE TEMP TABLE data_conflicts AS
SELECT 
    player_name,
    COUNT(DISTINCT license_number) FILTER (WHERE license_number IS NOT NULL) as license_conflicts,
    COUNT(DISTINCT fargo_rating) FILTER (WHERE fargo_rating IS NOT NULL) as fargo_conflicts,
    COUNT(DISTINCT country) FILTER (WHERE country IS NOT NULL) as country_conflicts,
    string_agg(DISTINCT license_number || ' (' || ranking_system || ')', ', ' 
        ORDER BY license_number || ' (' || ranking_system || ')') 
        FILTER (WHERE license_number IS NOT NULL) as license_details,
    string_agg(DISTINCT fargo_rating::text || ' (' || ranking_system || ')', ', ' 
        ORDER BY fargo_rating::text || ' (' || ranking_system || ')') 
        FILTER (WHERE fargo_rating IS NOT NULL) as fargo_details,
    string_agg(DISTINCT country || ' (' || ranking_system || ')', ', ' 
        ORDER BY country || ' (' || ranking_system || ')') 
        FILTER (WHERE country IS NOT NULL) as country_details
FROM rankings
WHERE player_name IN (SELECT player_name FROM cross_system_players)
GROUP BY player_name;

\echo ''
\echo '================================================================================';
\echo 'CONFLICT DETECTION REPORT';
\echo '================================================================================';
\echo ''

-- Report players with conflicts
\echo '--- PLAYERS WITH CONFLICTING DATA (WILL BE SKIPPED) ---';
SELECT 
    player_name,
    CASE WHEN license_conflicts > 1 THEN 'LICENSE CONFLICT: ' || license_details ELSE '' END as license_issue,
    CASE WHEN fargo_conflicts > 1 THEN 'FARGO CONFLICT: ' || fargo_details ELSE '' END as fargo_issue,
    CASE WHEN country_conflicts > 1 THEN 'COUNTRY CONFLICT: ' || country_details ELSE '' END as country_issue
FROM data_conflicts
WHERE license_conflicts > 1 OR fargo_conflicts > 1 OR country_conflicts > 1
ORDER BY player_name;

\echo ''
\echo '--- PLAYERS SAFE TO MERGE (NO CONFLICTS) ---';
SELECT player_name
FROM data_conflicts
WHERE license_conflicts <= 1 AND fargo_conflicts <= 1 AND country_conflicts <= 1
ORDER BY player_name;

-- Step 3: Create safe merge list (no conflicts)
CREATE TEMP TABLE safe_to_merge AS
SELECT player_name
FROM data_conflicts
WHERE license_conflicts <= 1 
    AND fargo_conflicts <= 1 
    AND country_conflicts <= 1;

-- Step 4: Calculate best values for safe players only
CREATE TEMP TABLE player_best_values AS
SELECT 
    r.player_name,
    -- Take first non-null license
    (array_agg(r.license_number ORDER BY 
        CASE WHEN r.license_number IS NOT NULL THEN 0 ELSE 1 END,
        r.snapshot_date DESC)
    )[1] as best_license,
    -- Take highest fargo rating
    MAX(r.fargo_rating) as best_fargo,
    -- Take first non-null country
    (array_agg(r.country ORDER BY 
        CASE WHEN r.country IS NOT NULL THEN 0 ELSE 1 END,
        r.snapshot_date DESC)
    )[1] as best_country
FROM rankings r
INNER JOIN safe_to_merge stm ON r.player_name = stm.player_name
GROUP BY r.player_name;

\echo ''
\echo '================================================================================';
\echo 'SAFE MERGE PREVIEW';
\echo '================================================================================';
\echo ''

-- Show what will be updated
SELECT 
    r.player_name,
    r.ranking_system,
    CASE 
        WHEN r.license_number IS NULL AND pbv.best_license IS NOT NULL 
        THEN 'LICENSE: NULL → ' || pbv.best_license
        ELSE NULL
    END as license_update,
    CASE 
        WHEN r.fargo_rating IS NULL AND pbv.best_fargo IS NOT NULL 
        THEN 'FARGO: NULL → ' || pbv.best_fargo::text
        ELSE NULL
    END as fargo_update,
    CASE 
        WHEN r.country IS NULL AND pbv.best_country IS NOT NULL 
        THEN 'COUNTRY: NULL → ' || pbv.best_country
        ELSE NULL
    END as country_update
FROM rankings r
INNER JOIN player_best_values pbv ON r.player_name = pbv.player_name
WHERE 
    (r.license_number IS NULL AND pbv.best_license IS NOT NULL)
    OR (r.fargo_rating IS NULL AND pbv.best_fargo IS NOT NULL)
    OR (r.country IS NULL AND pbv.best_country IS NOT NULL)
ORDER BY r.player_name, r.ranking_system;

-- Step 5: Perform safe updates only
UPDATE rankings r
SET license_number = pbv.best_license
FROM player_best_values pbv
WHERE r.player_name = pbv.player_name
    AND r.license_number IS NULL
    AND pbv.best_license IS NOT NULL;

UPDATE rankings r
SET fargo_rating = pbv.best_fargo
FROM player_best_values pbv
WHERE r.player_name = pbv.player_name
    AND r.fargo_rating IS NULL
    AND pbv.best_fargo IS NOT NULL;

UPDATE rankings r
SET country = pbv.best_country
FROM player_best_values pbv
WHERE r.player_name = pbv.player_name
    AND r.country IS NULL
    AND pbv.best_country IS NOT NULL;

-- Show summary
\echo ''
\echo '================================================================================';
\echo 'UPDATE SUMMARY';
\echo '================================================================================';
\echo ''

SELECT 
    (SELECT COUNT(*) FROM safe_to_merge) as players_merged,
    (SELECT COUNT(*) FROM data_conflicts 
     WHERE license_conflicts > 1 OR fargo_conflicts > 1 OR country_conflicts > 1) as players_skipped_conflicts;

-- Refresh materialized view
REFRESH MATERIALIZED VIEW mv_latest_rankings;

\echo ''
\echo '✓ Materialized view refreshed';
\echo ''

COMMIT;

\echo '================================================================================';
\echo 'SAFE CROSS-SYSTEM ENRICHMENT COMPLETE';
\echo '================================================================================';
\echo '';
\echo 'IMPORTANT: Review conflicting players above and resolve manually.';
\echo 'Conflicts may indicate:';
\echo '  1. Data entry errors in source ranking systems';
\echo '  2. Different players with identical names';
\echo '  3. Name variations that need disambiguation';
\echo '';
