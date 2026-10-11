-- Manual Conflict Resolution Script
-- 
-- For players with conflicting data across systems, this script helps
-- identify and manually resolve conflicts.

\echo '';
\echo '================================================================================';
\echo 'CONFLICT INVESTIGATION REPORT';
\echo '================================================================================';
\echo '';

-- Show all details for conflicting players
\echo '--- DETAILED VIEW OF ALL CONFLICTS ---';
\echo '';

WITH conflicting_players AS (
    SELECT 
        player_name,
        COUNT(DISTINCT license_number) FILTER (WHERE license_number IS NOT NULL) as license_conflicts,
        COUNT(DISTINCT country) FILTER (WHERE country IS NOT NULL) as country_conflicts
    FROM rankings
    WHERE player_name IN (
        SELECT player_name 
        FROM rankings 
        GROUP BY player_name 
        HAVING COUNT(DISTINCT ranking_system) > 1
    )
    GROUP BY player_name
    HAVING COUNT(DISTINCT license_number) FILTER (WHERE license_number IS NOT NULL) > 1
        OR COUNT(DISTINCT country) FILTER (WHERE country IS NOT NULL) > 1
)
SELECT 
    r.player_name,
    r.ranking_system,
    r.rank,
    r.license_number,
    r.fargo_rating,
    r.country,
    r.snapshot_date,
    r.created_at
FROM rankings r
INNER JOIN conflicting_players cp ON r.player_name = cp.player_name
ORDER BY r.player_name, r.ranking_system;

\echo '';
\echo '================================================================================';
\echo 'RECOMMENDED ACTIONS';
\echo '================================================================================';
\echo '';
\echo 'For each conflict above, verify:';
\echo '  1. Are these the same player? Check:';
\echo '     - Same license number (even if slightly different format)';
\echo '     - Similar Fargo ratings (within 50 points)';
\echo '     - Similar ranking level';
\echo '';
\echo '  2. If SAME PLAYER with conflicting data:';
\echo '     - Research correct country/license on official websites';
\echo '     - Update incorrect record manually';
\echo '';
\echo '  3. If DIFFERENT PLAYERS with same name:';
\echo '     - Add player_id or unique identifier system';
\echo '     - Keep records separate';
\echo '';

-- Example resolution queries (commented out - uncomment and edit as needed)
\echo '-- EXAMPLE RESOLUTION QUERIES --';
\echo '-- (Uncomment and edit with correct values)';
\echo '';
\echo '-- Fix Chris Melling country (if ENG is correct):';
\echo '-- UPDATE rankings SET country = ''ENG'' WHERE player_name = ''Chris Melling'' AND ranking_system = ''WPA_Heyball_Men'';';
\echo '';
\echo '-- Fix Joseph Faul country (check which is correct):';
\echo '-- UPDATE rankings SET country = ''RSA'' WHERE player_name = ''Joseph Faul'' AND ranking_system = ''WPA_Heyball_Men'';';
\echo '-- OR';
\echo '-- UPDATE rankings SET country = ''GBR'' WHERE player_name = ''Joseph Faul'' AND ranking_system = ''WPA_Men'';';
\echo '';
\echo '-- Fix Katarzyna Wesolowska country (if POL is correct):';
\echo '-- UPDATE rankings SET country = ''POL'' WHERE player_name = ''Katarzyna Wesolowska'' AND ranking_system = ''WPA_Women'';';
\echo '';
