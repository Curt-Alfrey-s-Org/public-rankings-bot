-- Test Center Postgres bootstrap: same logical schema as production for rankings / history / hot-streak reads.
-- Order is valid on fresh DB (MVs after base tables). Loaded after extensions in init-testcenter-database.sql
-- or as docker-entrypoint-initdb.d/02-schema.sql.

-- Players (tournament-style; matches get_leaderboard_from_rankings / get_fargo_hot_streak_players)
CREATE TABLE IF NOT EXISTS players (
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
CREATE INDEX IF NOT EXISTS idx_players_license ON players(license_number);
CREATE INDEX IF NOT EXISTS idx_players_player_id ON players(player_id);

-- Rankings (wide column set for get_rankings_paginated / save_rankings)
CREATE TABLE IF NOT EXISTS rankings (
    id SERIAL PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL,
    ranking_system VARCHAR(64) NOT NULL,
    rank INTEGER NOT NULL,
    points DOUBLE PRECISION NOT NULL,
    country VARCHAR(255),
    snapshot_date DATE NOT NULL,
    license_number VARCHAR(255),
    fargo_rating DOUBLE PRECISION,
    fargo_last_updated TIMESTAMP,
    stops_played INTEGER DEFAULT 0,
    position INTEGER,
    source_data JSONB DEFAULT '{}'::jsonb,
    alfa_rating DOUBLE PRECISION,
    fargo_robustness INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Matches production Alembic 027: one row per list position, not per player name
    UNIQUE(ranking_system, snapshot_date, rank)
);
CREATE INDEX IF NOT EXISTS idx_rankings_date ON rankings(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_rankings_player ON rankings(player_name);
CREATE INDEX IF NOT EXISTS idx_rankings_system ON rankings(ranking_system);

CREATE TABLE IF NOT EXISTS ranking_changes (
    id SERIAL PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL,
    ranking_system VARCHAR(32) NOT NULL,
    old_rank INTEGER,
    new_rank INTEGER,
    old_points DOUBLE PRECISION,
    new_points DOUBLE PRECISION,
    change_date DATE NOT NULL,
    change_type VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actor_role VARCHAR(64) NOT NULL,
    actor_subject VARCHAR(255) NOT NULL,
    action VARCHAR(128) NOT NULL,
    details TEXT
);

CREATE TABLE IF NOT EXISTS tournament_history (
    id SERIAL PRIMARY KEY,
    tournament_id VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    date DATE,
    location VARCHAR(255),
    year INTEGER,
    association VARCHAR(32),
    championship VARCHAR(255),
    champion VARCHAR(255),
    runner_up VARCHAR(255),
    final_score VARCHAR(64),
    status VARCHAR(32) DEFAULT 'completed',
    prize_pool VARCHAR(128),
    source_url TEXT,
    bracket_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tournament_history_tournament_id ON tournament_history(tournament_id);
CREATE INDEX IF NOT EXISTS idx_tournament_history_year ON tournament_history(year);
CREATE INDEX IF NOT EXISTS idx_tournament_history_date ON tournament_history(date);

CREATE TABLE IF NOT EXISTS tournament_results (
    id SERIAL PRIMARY KEY,
    tournament_id VARCHAR(255) NOT NULL REFERENCES tournament_history(tournament_id) ON DELETE CASCADE,
    player_name VARCHAR(255) NOT NULL,
    placement INTEGER,
    points DOUBLE PRECISION DEFAULT 0.0,
    fargo_rating_at_scrape DOUBLE PRECISION,
    stops_played INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tournament_id, player_name)
);
CREATE INDEX IF NOT EXISTS idx_tournament_results_tournament ON tournament_results(tournament_id);
CREATE INDEX IF NOT EXISTS idx_tournament_results_player ON tournament_results(player_name);

CREATE TABLE IF NOT EXISTS tournament_history_matches (
    id SERIAL PRIMARY KEY,
    tournament_id VARCHAR(255) NOT NULL REFERENCES tournament_history(tournament_id) ON DELETE CASCADE,
    operator_name VARCHAR(255) NOT NULL,
    player2_name VARCHAR(255) NOT NULL,
    operator_score INTEGER,
    player2_score INTEGER,
    winner_name VARCHAR(255),
    round_num VARCHAR(128),
    match_num INTEGER,
    match_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tournament_history_matches_tournament ON tournament_history_matches(tournament_id);

CREATE TABLE IF NOT EXISTS fargo_rating_history (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(255) NOT NULL,
    player_name VARCHAR(255) NOT NULL,
    ranking_system VARCHAR(32),
    old_fargo_rating DOUBLE PRECISION,
    new_fargo_rating DOUBLE PRECISION NOT NULL,
    fargo_source VARCHAR(64),
    snapshot_date DATE NOT NULL,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archive_reason VARCHAR(64) DEFAULT 'update',
    confidence_score DOUBLE PRECISION DEFAULT 0.8,
    data_quality VARCHAR(32) DEFAULT 'verified'
);
CREATE INDEX IF NOT EXISTS idx_fargo_history_player_date ON fargo_rating_history(player_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_fargo_history_player_name ON fargo_rating_history(player_name);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_latest_rankings AS
SELECT player_name AS name, rank, points, country, snapshot_date, ranking_system, license_number, fargo_rating
FROM rankings r
WHERE snapshot_date = (
    SELECT MAX(r2.snapshot_date) FROM rankings r2 WHERE r2.ranking_system = r.ranking_system
)
ORDER BY ranking_system, rank ASC;
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_latest_rankings_unique
    ON mv_latest_rankings (ranking_system, rank, snapshot_date, name);
CREATE INDEX IF NOT EXISTS idx_mv_latest_rankings_system
    ON mv_latest_rankings (ranking_system);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_tournament_history_recent AS
SELECT id, tournament_id, name, year, date, location, association, championship, prize_pool, status
FROM tournament_history;
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_tournament_history_recent_id
    ON mv_tournament_history_recent (tournament_id);
CREATE INDEX IF NOT EXISTS idx_mv_tournament_history_recent_date
    ON mv_tournament_history_recent (date DESC);

-- Test tournament workflow tables (same as schema_postgres TEST section)
CREATE TABLE IF NOT EXISTS test_tournaments (
    id SERIAL PRIMARY KEY,
    tournament_id VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    format VARCHAR(64) NOT NULL DEFAULT 'single_elimination',
    max_players INTEGER NOT NULL DEFAULT 32,
    entry_fee INTEGER NOT NULL DEFAULT 1000,
    prize_pool INTEGER NOT NULL DEFAULT 32000,
    tables INTEGER NOT NULL DEFAULT 8,
    race_to INTEGER NOT NULL DEFAULT 9,
    race_to_final INTEGER DEFAULT 10,
    status VARCHAR(64) NOT NULL DEFAULT 'registration',
    location VARCHAR(255),
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    points_structure TEXT,
    notes TEXT,
    ranking_system VARCHAR(32),
    game_type VARCHAR(64),
    association VARCHAR(64),
    bracket_template_id INTEGER,
    bracket_draw_size INTEGER,
    bye_strategy VARCHAR(32) DEFAULT 'top_seed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_test_tournaments_status ON test_tournaments(status);

CREATE TABLE IF NOT EXISTS test_tournament_players (
    id SERIAL PRIMARY KEY,
    tournament_id VARCHAR(255) NOT NULL,
    player_id VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    nickname VARCHAR(50),
    fargo_rating DECIMAL(6,2),
    current_rating DECIMAL(8,2) DEFAULT 1500.00,
    country VARCHAR(3),
    status VARCHAR(32) DEFAULT 'registered',
    seed INTEGER,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tournament_id) REFERENCES test_tournaments(tournament_id) ON DELETE CASCADE,
    UNIQUE(tournament_id, player_id)
);

CREATE TABLE IF NOT EXISTS test_tournament_matches (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(255) NOT NULL UNIQUE,
    tournament_id VARCHAR(255) NOT NULL,
    bracket_type VARCHAR(32) DEFAULT 'winners',
    round_number INTEGER NOT NULL DEFAULT 1,
    operator_id VARCHAR(255),
    player2_id VARCHAR(255),
    operator_name VARCHAR(255),
    player2_name VARCHAR(255),
    operator_score INTEGER DEFAULT 0,
    player2_score INTEGER DEFAULT 0,
    winner_id VARCHAR(255),
    status VARCHAR(32) DEFAULT 'pending',
    table_number INTEGER,
    scheduled_time TIMESTAMP,
    race_to INTEGER DEFAULT 9,
    handicap1 INTEGER DEFAULT 0,
    handicap2 INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tournament_id) REFERENCES test_tournaments(tournament_id) ON DELETE CASCADE
);

COMMENT ON SCHEMA public IS 'Rankings Bot Test Center — isolated instance; mirrors production table shapes for view testing.';
