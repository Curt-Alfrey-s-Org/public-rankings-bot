-- PostgreSQL initialization script for Rankings Bot
-- This script is automatically run by Docker on first startup

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Note: Additional tables and indexes will be created by the application
-- via SQLAlchemy ORM models during the first API startup.

-- Helpful indexes for rankings (created during migrations if needed):
-- CREATE INDEX IF NOT EXISTS idx_rankings_player_id ON rankings(player_id);
-- CREATE INDEX IF NOT EXISTS idx_rankings_tournament_id ON rankings(tournament_id);
-- CREATE INDEX IF NOT EXISTS idx_rankings_association ON rankings(association);
-- CREATE INDEX IF NOT EXISTS idx_rankings_created_at ON rankings(created_at);

-- Create comment documenting this schema
COMMENT ON SCHEMA public IS 'Rankings Bot PostgreSQL schema';
