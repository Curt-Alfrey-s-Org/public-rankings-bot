-- Add license_number to v_current_rankings for Leaderboard display
-- Run: psql $DATABASE_URL -f database/migrations/add_license_to_v_current_rankings.sql

DROP VIEW IF EXISTS v_current_rankings CASCADE;

CREATE VIEW v_current_rankings AS
SELECT
    p.player_id,
    p.first_name,
    p.last_name,
    p.nickname,
    p.license_number,
    p.avatar_url,
    p.total_points,
    p.current_rank,
    p.total_tournaments_played,
    p.hall_of_fame,
    p.hot_streak_count,
    p.fargo_score,
    p.nationality,
    ps.win_percentage_matches,
    ps.win_percentage_games,
    ps.first_place_finishes,
    ps.second_place_finishes,
    ps.third_place_finishes
FROM players p
LEFT JOIN player_statistics ps ON p.player_id = ps.player_id
WHERE p.membership_status = 'active'
ORDER BY p.current_rank ASC NULLS LAST, p.total_points DESC;
