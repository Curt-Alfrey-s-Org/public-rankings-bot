-- Migration: Add tables_available to tournaments
-- Date: 2026-02-21
-- Description: Adds tables_available column for table assignment support

ALTER TABLE tournaments
ADD COLUMN IF NOT EXISTS tables_available INTEGER;

COMMENT ON COLUMN tournaments.tables_available IS 'Number of tables available for the tournament';
