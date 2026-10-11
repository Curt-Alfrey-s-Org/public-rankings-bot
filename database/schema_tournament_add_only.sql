-- Add tournament management tables to existing ranked-players Postgres DB
-- Creates tournaments and matches tables with stage2 support
-- Does NOT drop existing tables

CREATE TABLE IF NOT EXISTS tournaments (
    id SERIAL PRIMARY KEY,
    tournament_id VARCHAR(32) UNIQUE NOT NULL,
    tournament_name VARCHAR(255) NOT NULL,
    tournament_date DATE NOT NULL,
    location VARCHAR(255),
    elimination_type VARCHAR(32) NOT NULL,
    max_players INTEGER DEFAULT 32,
    tables_available INTEGER,
    actual_players INTEGER DEFAULT 0,
    points_structure TEXT,
    status VARCHAR(32) DEFAULT 'setup',
    created_by VARCHAR(255),
    winner_player_id VARCHAR(32),
    runner_up_player_id VARCHAR(32),
    notes TEXT,
    stage2_cutoff INTEGER,
    stage2_elimination_type VARCHAR(32),
    stage2_seed_strategy VARCHAR(32),
    stage2_started_at TIMESTAMP,
    match_time_limit_minutes INTEGER,
    shot_clock_seconds INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tournaments_date ON tournaments(tournament_date DESC);
CREATE INDEX IF NOT EXISTS idx_tournaments_status ON tournaments(status);
CREATE INDEX IF NOT EXISTS idx_tournaments_tournament_id ON tournaments(tournament_id);

CREATE TABLE IF NOT EXISTS tournament_players (
    id SERIAL PRIMARY KEY,
    tournament_id VARCHAR(32) NOT NULL REFERENCES tournaments(tournament_id),
    player_id VARCHAR(32) NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_tournament_players_tournament ON tournament_players(tournament_id);
CREATE INDEX IF NOT EXISTS idx_tournament_players_player ON tournament_players(player_id);
CREATE INDEX IF NOT EXISTS idx_tournament_players_placement ON tournament_players(tournament_id, final_placement);

CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(64) UNIQUE NOT NULL,
    tournament_id VARCHAR(32) NOT NULL REFERENCES tournaments(tournament_id),
    round_number INTEGER NOT NULL,
    match_number INTEGER NOT NULL,
    bracket_type VARCHAR(32) DEFAULT 'winners',
    operator_id VARCHAR(32),
    player2_id VARCHAR(32),
    operator_score INTEGER DEFAULT 0,
    player2_score INTEGER DEFAULT 0,
    winner_id VARCHAR(32),
    loser_id VARCHAR(32),
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

CREATE INDEX IF NOT EXISTS idx_matches_tournament ON matches(tournament_id);
CREATE INDEX IF NOT EXISTS idx_matches_round ON matches(tournament_id, round_number);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_matches_match_id ON matches(match_id);
CREATE INDEX IF NOT EXISTS idx_matches_operator ON matches(operator_id);
CREATE INDEX IF NOT EXISTS idx_matches_player2 ON matches(player2_id);

CREATE TABLE IF NOT EXISTS games (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(64) NOT NULL REFERENCES matches(match_id),
    game_number INTEGER NOT NULL,
    winner_id VARCHAR(32),
    breaking_player_id VARCHAR(32),
    innings INTEGER,
    run_out INTEGER DEFAULT 0,
    break_and_run INTEGER DEFAULT 0,
    notes TEXT,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(match_id, game_number)
);

CREATE INDEX IF NOT EXISTS idx_games_match ON games(match_id);
