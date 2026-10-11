#!/usr/bin/env python3
"""
Check for legacy duplicate index name idx_expires_at in the database.
If present, it can cause migration 001 to fail with "relation idx_expires_at already exists".
Run from project root: python scripts/check_duplicate_index.py
Uses DATABASE_URL from env or .env.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

env_file = os.path.join(PROJECT_ROOT, ".env")
if os.path.isfile(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def main():
    from sqlalchemy import text
    from database import engine

    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT indexname, tablename
            FROM pg_indexes
            WHERE schemaname = 'public' AND indexname = 'idx_expires_at'
        """))
        rows = r.fetchall()

    if not rows:
        print("No legacy index idx_expires_at found. Safe to run: alembic upgrade head")
        return 0

    print("Legacy index idx_expires_at found (can cause migration 001 to fail):")
    for indexname, tablename in rows:
        print(f"  {indexname} on table {tablename}")
    print("\nFix: run 'alembic upgrade head'. Migration 001 will DROP INDEX IF EXISTS idx_expires_at and create tables with unique index names.")
    return 1

if __name__ == "__main__":
    sys.exit(main())
