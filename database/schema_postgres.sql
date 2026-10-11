-- Rankings Bot schema for PostgreSQL (see docs/DATABASE_UPGRADE.md)
-- Run after Alembic/auth tables. Creates rankings/tournament tables in same DB.

-- Players table
CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    nationality VARCHAR(255),
    fargo_rating INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Rankings snapshots (daily)
CREATE TABLE IF NOT EXISTS rankings (
    id SERIAL PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL,
    ranking_system VARCHAR(32) NOT NULL,
    rank INTEGER NOT NULL,
    points DOUBLE PRECISION NOT NULL,
    country VARCHAR(255),
    snapshot_date DATE NOT NULL,
    license_number VARCHAR(255),
    fargo_rating DOUBLE PRECISION,
    fargo_last_updated TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_name, ranking_system, snapshot_date),
    CHECK (ranking_system IN ('WPBA_Women', 'WPA_Men', 'WPA_Women', 'WPBA', 'WPA', 'WPA_Heyball', 'WPA_Heyball_Men', 'WPA_Heyball_Women', 'WPA_Artistic'))
);

-- Rankings archive: immutable historical records (production resilience)
-- Stores every version of a ranking before it's updated, enabling data recovery
-- Triggered by data updates, deletions, or corrections
CREATE TABLE IF NOT EXISTS rankings_archive (
    id SERIAL PRIMARY KEY,
    original_id INTEGER NOT NULL,
    player_name VARCHAR(255) NOT NULL,
    ranking_system VARCHAR(32) NOT NULL,
    rank INTEGER NOT NULL,
    points DOUBLE PRECISION NOT NULL,
    country VARCHAR(255),
    snapshot_date DATE NOT NULL,
    license_number VARCHAR(255),
    fargo_rating DOUBLE PRECISION,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archive_reason VARCHAR(64) DEFAULT 'update',
    CHECK (archive_reason IN ('update', 'delete', 'correction', 'pre_update'))
);
CREATE INDEX IF NOT EXISTS idx_rankings_archive_player ON rankings_archive(player_name);
CREATE INDEX IF NOT EXISTS idx_rankings_archive_date ON rankings_archive(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_rankings_archive_archived_at ON rankings_archive(archived_at DESC);
CREATE INDEX IF NOT EXISTS idx_rankings_archive_original_id ON rankings_archive(original_id);

-- Organization metadata
CREATE TABLE IF NOT EXISTS org_metadata (
    id SERIAL PRIMARY KEY,
    org_code VARCHAR(32) NOT NULL UNIQUE,
    org_name VARCHAR(255) NOT NULL,
    url TEXT,
    logo_url TEXT,
    primary_color VARCHAR(64),
    secondary_color VARCHAR(64),
    theme TEXT,
    layout TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ranking types metadata
CREATE TABLE IF NOT EXISTS ranking_types (
    id SERIAL PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    org_code VARCHAR(32) NOT NULL,
    division VARCHAR(32) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ranking changes
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

-- Audit log (if not created by Alembic)
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actor_role VARCHAR(64) NOT NULL,
    actor_subject VARCHAR(255) NOT NULL,
    action VARCHAR(128) NOT NULL,
    details TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC);

-- Auth sessions: store login tokens for server-side validation (see docs/PRODUCTION_AND_APP_CONVERSION.md)
CREATE TABLE IF NOT EXISTS auth_sessions (
    id SERIAL PRIMARY KEY,
    token VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL CHECK (role IN ('user', 'admin')),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON auth_sessions(token);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions(expires_at);

CREATE INDEX IF NOT EXISTS idx_rankings_date ON rankings(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_rankings_player ON rankings(player_name);
CREATE INDEX IF NOT EXISTS idx_rankings_system ON rankings(ranking_system);
CREATE INDEX IF NOT EXISTS idx_changes_date ON ranking_changes(change_date);
CREATE INDEX IF NOT EXISTS idx_changes_player ON ranking_changes(player_name);

-- Materialized views for fast read paths (refresh after scrapes/updates)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_latest_rankings AS
SELECT player_name as name, rank, points, country, snapshot_date, ranking_system, license_number, fargo_rating
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

-- Email signup
CREATE TABLE IF NOT EXISTS email_rank_subscriptions (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    player_name VARCHAR(255) NOT NULL,
    ranking_system VARCHAR(32) NOT NULL,
    unsubscribe_token VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_player_system ON email_rank_subscriptions(player_name, ranking_system);
CREATE INDEX IF NOT EXISTS idx_subscriptions_token ON email_rank_subscriptions(unsubscribe_token);

-- Tournament definitions
CREATE TABLE IF NOT EXISTS tournament_definitions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    points_by_place TEXT NOT NULL,
    is_default_for_import INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tournament_definitions_name ON tournament_definitions(name);

-- Tournament imports
CREATE TABLE IF NOT EXISTS tournament_imports (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    raw_results TEXT NOT NULL,
    points_by_place TEXT,
    status VARCHAR(64) NOT NULL DEFAULT 'incomplete',
    ranking_system VARCHAR(32) NOT NULL DEFAULT 'WPBA',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tournament_imports_status ON tournament_imports(status);
CREATE INDEX IF NOT EXISTS idx_tournament_imports_created ON tournament_imports(created_at DESC);

-- Tournament history (past events: metadata, results, and match scores)
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
CREATE INDEX IF NOT EXISTS idx_tournament_history_association ON tournament_history(association);

-- Tournament results (placements per tournament; optional Fargo at scrape time)
CREATE TABLE IF NOT EXISTS tournament_results (
    id SERIAL PRIMARY KEY,
    tournament_id VARCHAR(255) NOT NULL REFERENCES tournament_history(tournament_id) ON DELETE CASCADE,
    player_name VARCHAR(255) NOT NULL,
    placement INTEGER,
    points DOUBLE PRECISION DEFAULT 0.0,
    fargo_rating_at_scrape DOUBLE PRECISION,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tournament_id, player_name)
);
CREATE INDEX IF NOT EXISTS idx_tournament_results_tournament ON tournament_results(tournament_id);
CREATE INDEX IF NOT EXISTS idx_tournament_results_player ON tournament_results(player_name);

-- Tournament history matches (for head-to-head and match scores)
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
CREATE INDEX IF NOT EXISTS idx_tournament_history_matches_operator ON tournament_history_matches(operator_name);
CREATE INDEX IF NOT EXISTS idx_tournament_history_matches_player2 ON tournament_history_matches(player2_name);
CREATE INDEX IF NOT EXISTS idx_tournament_history_matches_players ON tournament_history_matches(operator_name, player2_name);
CREATE INDEX IF NOT EXISTS idx_tournament_history_matches_date ON tournament_history_matches(match_date);

-- Rankings archive (historical data preservation)
CREATE TABLE IF NOT EXISTS rankings_archive (
    id SERIAL PRIMARY KEY,
    original_id INTEGER,
    player_name VARCHAR(255) NOT NULL,
    ranking_system VARCHAR(32) NOT NULL,
    rank INTEGER NOT NULL,
    points DOUBLE PRECISION NOT NULL,
    country VARCHAR(255),
    snapshot_date DATE NOT NULL,
    license_number VARCHAR(255),
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archive_reason VARCHAR(64) DEFAULT 'update'
);
CREATE INDEX IF NOT EXISTS idx_rankings_archive_player ON rankings_archive(player_name);
CREATE INDEX IF NOT EXISTS idx_rankings_archive_date ON rankings_archive(snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_rankings_archive_archived_at ON rankings_archive(archived_at DESC);

-- ==========================================
-- TEST TOURNAMENT TABLES (Isolated from live data)
-- ==========================================

-- Test tournament definitions (isolated from live tournaments)
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
CREATE INDEX IF NOT EXISTS idx_test_tournaments_created ON test_tournaments(created_at DESC);

-- Test tournament players (isolated from live players)
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
CREATE INDEX IF NOT EXISTS idx_test_tournament_players_tournament ON test_tournament_players(tournament_id);
CREATE INDEX IF NOT EXISTS idx_test_tournament_players_player ON test_tournament_players(player_id);

-- Test tournament matches (isolated from live matches)
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
CREATE INDEX IF NOT EXISTS idx_test_tournament_matches_tournament ON test_tournament_matches(tournament_id);
CREATE INDEX IF NOT EXISTS idx_test_tournament_matches_status ON test_tournament_matches(status);
CREATE INDEX IF NOT EXISTS idx_test_tournament_matches_round ON test_tournament_matches(round_number);
