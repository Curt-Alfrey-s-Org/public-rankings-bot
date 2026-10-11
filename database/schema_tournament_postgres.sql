-- Tournament management tables for PostgreSQL (fresh install; see docs/DATABASE_UPGRADE.md)
-- Run when "tournaments" table is missing. Replaces minimal "players" with full profile table.

DROP VIEW IF EXISTS v_current_rankings CASCADE;
DROP VIEW IF EXISTS v_tournament_standings CASCADE;
DROP VIEW IF EXISTS v_upcoming_matches CASCADE;
DROP TABLE IF EXISTS games CASCADE;
DROP TABLE IF EXISTS matches CASCADE;
DROP TABLE IF EXISTS tournament_players CASCADE;
DROP TABLE IF EXISTS ranking_history CASCADE;
DROP TABLE IF EXISTS player_statistics CASCADE;
DROP TABLE IF EXISTS tournaments CASCADE;
DROP TABLE IF EXISTS tournament_templates CASCADE;
DROP TABLE IF EXISTS players CASCADE;

CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(32) UNIQUE NOT NULL,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    nickname VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(64),
    license_number VARCHAR(64),
    avatar_url TEXT,
    fargo_score INTEGER,
    nationality VARCHAR(255),
    hometown VARCHAR(255),
    state VARCHAR(64),
    membership_status VARCHAR(32) DEFAULT 'active',
    hall_of_fame INTEGER DEFAULT 0,
    hot_streak_count INTEGER DEFAULT 0,
    total_tournaments_played INTEGER DEFAULT 0,
    total_points DOUBLE PRECISION DEFAULT 0.0,
    current_rank INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_players_license ON players(license_number);
CREATE INDEX idx_players_email ON players(email);
CREATE INDEX idx_players_player_id ON players(player_id);
CREATE INDEX idx_players_membership ON players(membership_status);
CREATE INDEX idx_players_rank ON players(current_rank);

CREATE TABLE tournament_templates (
    id SERIAL PRIMARY KEY,
    template_name VARCHAR(255) NOT NULL UNIQUE,
    elimination_type VARCHAR(32) NOT NULL,
    max_players INTEGER DEFAULT 32,
    points_structure TEXT NOT NULL,
    description TEXT,
    times_used INTEGER DEFAULT 0,
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_templates_name ON tournament_templates(template_name);

CREATE TABLE tournaments (
    id SERIAL PRIMARY KEY,
    tournament_id VARCHAR(32) UNIQUE NOT NULL,
    tournament_name VARCHAR(255) NOT NULL,
    tournament_date DATE NOT NULL,
    location VARCHAR(255),
    elimination_type VARCHAR(32) NOT NULL,
    max_players INTEGER DEFAULT 32,
    actual_players INTEGER DEFAULT 0,
    points_structure TEXT NOT NULL,
    status VARCHAR(32) DEFAULT 'setup',
    template_id INTEGER REFERENCES tournament_templates(id),
    created_by VARCHAR(255),
    winner_player_id VARCHAR(32) REFERENCES players(player_id),
    runner_up_player_id VARCHAR(32) REFERENCES players(player_id),
    notes TEXT,
    match_time_limit_minutes INTEGER,
    shot_clock_seconds INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
CREATE INDEX idx_tournaments_date ON tournaments(tournament_date DESC);
CREATE INDEX idx_tournaments_status ON tournaments(status);
CREATE INDEX idx_tournaments_tournament_id ON tournaments(tournament_id);

CREATE TABLE tournament_players (
    id SERIAL PRIMARY KEY,
    tournament_id VARCHAR(32) NOT NULL REFERENCES tournaments(tournament_id),
    player_id VARCHAR(32) NOT NULL REFERENCES players(player_id),
    seed_position INTEGER,
    final_placement INTEGER,
    points_earned DOUBLE PRECISION DEFAULT 0.0,
    matches_played INTEGER DEFAULT 0,
    matches_won INTEGER DEFAULT 0,
    matches_lost INTEGER DEFAULT 0,
    total_games_won INTEGER DEFAULT 0,
    total_games_lost INTEGER DEFAULT 0,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tournament_id, player_id)
);
CREATE INDEX idx_tournament_players_tournament ON tournament_players(tournament_id);
CREATE INDEX idx_tournament_players_player ON tournament_players(player_id);
CREATE INDEX idx_tournament_players_placement ON tournament_players(tournament_id, final_placement);

CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(64) UNIQUE NOT NULL,
    tournament_id VARCHAR(32) NOT NULL REFERENCES tournaments(tournament_id),
    round_number INTEGER NOT NULL,
    match_number INTEGER NOT NULL,
    bracket_type VARCHAR(32) DEFAULT 'winners',
    operator_id VARCHAR(32) REFERENCES players(player_id),
    player2_id VARCHAR(32) REFERENCES players(player_id),
    operator_score INTEGER DEFAULT 0,
    player2_score INTEGER DEFAULT 0,
    winner_id VARCHAR(32) REFERENCES players(player_id),
    loser_id VARCHAR(32) REFERENCES players(player_id),
    status VARCHAR(32) DEFAULT 'pending',
    race_to INTEGER,
    scheduled_time TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    table_number INTEGER,
    notes TEXT,
    is_forfeit INTEGER DEFAULT 0,
    forfeit_reason VARCHAR(64),
    forfeit_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_matches_tournament ON matches(tournament_id);
CREATE INDEX idx_matches_round ON matches(tournament_id, round_number);
CREATE INDEX idx_matches_status ON matches(status);
CREATE INDEX idx_matches_match_id ON matches(match_id);
CREATE INDEX idx_matches_operator ON matches(operator_id);
CREATE INDEX idx_matches_player2 ON matches(player2_id);

CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(64) NOT NULL REFERENCES matches(match_id),
    game_number INTEGER NOT NULL,
    winner_id VARCHAR(32) REFERENCES players(player_id),
    breaking_player_id VARCHAR(32) REFERENCES players(player_id),
    innings INTEGER,
    run_out INTEGER DEFAULT 0,
    break_and_run INTEGER DEFAULT 0,
    notes TEXT,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(match_id, game_number)
);
CREATE INDEX idx_games_match ON games(match_id);

CREATE TABLE player_statistics (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(32) NOT NULL UNIQUE REFERENCES players(player_id),
    total_tournaments INTEGER DEFAULT 0,
    total_matches_played INTEGER DEFAULT 0,
    total_matches_won INTEGER DEFAULT 0,
    total_games_played INTEGER DEFAULT 0,
    total_games_won INTEGER DEFAULT 0,
    win_percentage_matches DOUBLE PRECISION DEFAULT 0.0,
    win_percentage_games DOUBLE PRECISION DEFAULT 0.0,
    total_break_and_runs INTEGER DEFAULT 0,
    total_run_outs INTEGER DEFAULT 0,
    first_place_finishes INTEGER DEFAULT 0,
    second_place_finishes INTEGER DEFAULT 0,
    third_place_finishes INTEGER DEFAULT 0,
    average_placement DOUBLE PRECISION,
    best_placement INTEGER,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_player_stats_player ON player_statistics(player_id);

CREATE TABLE score_keeper_assignments (
    id SERIAL PRIMARY KEY,
    assignment_id VARCHAR(64) UNIQUE NOT NULL,
    tournament_id VARCHAR(32) NOT NULL REFERENCES tournaments(tournament_id),
    user_id VARCHAR(255) NOT NULL,
    table_number INTEGER,
    round_number INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_score_keeper_assignments_tournament ON score_keeper_assignments(tournament_id);
CREATE INDEX idx_score_keeper_assignments_user ON score_keeper_assignments(user_id);
CREATE INDEX idx_score_keeper_assignments_table ON score_keeper_assignments(table_number);

CREATE TABLE ranking_history (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(32) NOT NULL REFERENCES players(player_id),
    rank_position INTEGER NOT NULL,
    total_points DOUBLE PRECISION NOT NULL,
    tournaments_counted INTEGER DEFAULT 0,
    snapshot_date DATE NOT NULL,
    ranking_system VARCHAR(32) DEFAULT 'LOCAL',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, snapshot_date, ranking_system)
);
CREATE INDEX idx_ranking_history_player ON ranking_history(player_id);
CREATE INDEX idx_ranking_history_date ON ranking_history(snapshot_date DESC);

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

CREATE VIEW v_tournament_standings AS
SELECT
    tp.tournament_id,
    t.tournament_name,
    t.tournament_date,
    tp.player_id,
    p.first_name || ' ' || p.last_name AS player_name,
    p.nickname,
    tp.seed_position,
    tp.final_placement,
    tp.points_earned,
    tp.matches_played,
    tp.matches_won,
    tp.matches_lost,
    tp.total_games_won,
    tp.total_games_lost
FROM tournament_players tp
JOIN tournaments t ON tp.tournament_id = t.tournament_id
JOIN players p ON tp.player_id = p.player_id
ORDER BY tp.tournament_id, tp.final_placement;

CREATE VIEW v_upcoming_matches AS
SELECT
    m.match_id,
    m.tournament_id,
    t.tournament_name,
    m.round_number,
    m.match_number,
    m.bracket_type,
    p1.first_name || ' ' || p1.last_name AS operator_name,
    p2.first_name || ' ' || p2.last_name AS player2_name,
    m.scheduled_time,
    m.table_number,
    m.race_to
FROM matches m
JOIN tournaments t ON m.tournament_id = t.tournament_id
LEFT JOIN players p1 ON m.operator_id = p1.player_id
LEFT JOIN players p2 ON m.player2_id = p2.player_id
WHERE m.status IN ('pending', 'in_progress')
ORDER BY m.scheduled_time;

INSERT INTO tournament_templates (template_name, elimination_type, max_players, points_structure, description)
VALUES (
    'Standard 32-Player Single Elimination',
    'single',
    32,
    '{"1": 2880, "2": 3600, "3": 2500, "4": 2500, "5": 1800, "6": 1800, "7": 1800, "8": 1800, "9": 1200, "10": 1200, "11": 1200, "12": 1200, "13": 1200, "14": 1200, "15": 1200, "16": 1200}',
    'Standard 32-player single elimination with typical point distribution'
)
ON CONFLICT (template_name) DO NOTHING;

INSERT INTO tournament_templates (template_name, elimination_type, max_players, points_structure, description)
VALUES (
    'Standard 32-Player Double Elimination',
    'double',
    32,
    '{"1": 4320, "2": 3600, "3": 2880, "4": 2500, "5": 2160, "6": 2160, "7": 1800, "8": 1800, "9": 1440, "10": 1440, "11": 1440, "12": 1440, "13": 1200, "14": 1200, "15": 1200, "16": 1200}',
    'Standard 32-player double elimination with higher points for winners bracket'
)
ON CONFLICT (template_name) DO NOTHING;
