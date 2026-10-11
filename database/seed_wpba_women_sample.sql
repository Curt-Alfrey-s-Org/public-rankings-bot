-- Seed a few WPBA Women rankings for local/dev so the app shows data without scraping.
-- Run once: cat database/seed_wpba_women_sample.sql | docker exec -i rankings-bot-postgres psql -U rankingsbot_user -d rankingsbot
-- Uses today's date; safe to run multiple times (INSERT ... ON CONFLICT DO NOTHING).

INSERT INTO rankings (
    player_name,
    ranking_system,
    rank,
    points,
    country,
    snapshot_date,
    position,
    stops_played,
    source_data
) VALUES
    ('Kristina Tkach', 'WPBA_Women', 1, 1250.0, 'RUS', CURRENT_DATE, 1, 8, '{}'),
    ('Kelly Fisher', 'WPBA_Women', 2, 1180.0, 'GBR', CURRENT_DATE, 2, 8, '{}'),
    ('Jasmin Ouschan', 'WPBA_Women', 3, 1100.0, 'AUT', CURRENT_DATE, 3, 8, '{}'),
    ('Chezka Centeno', 'WPBA_Women', 4, 1020.0, 'PHI', CURRENT_DATE, 4, 7, '{}'),
    ('Allison Fisher', 'WPBA_Women', 5, 980.0, 'GBR', CURRENT_DATE, 5, 7, '{}')
ON CONFLICT (player_name, ranking_system, snapshot_date) DO NOTHING;
