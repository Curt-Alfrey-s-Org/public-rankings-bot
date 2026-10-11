#!/usr/bin/env python3
"""
Verify rankings-bot ORM database schema: compare actual DB to expected models.
Run from project root: python scripts/verify_db_schema.py
Uses same DATABASE_URL as the app (database package).
"""
import os
import sys

# Project root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Use same env as app (e.g. .env)
env_file = os.path.join(PROJECT_ROOT, ".env")
if os.path.isfile(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().replace('"', "").replace("'", ""))

from sqlalchemy import inspect, text

def main():
    from database import engine

    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())

    # Expected tables from ORM models (database.Base)
    from database import Base
    from api.models.user import User
    from api.models.auth_token import EmailVerificationToken, PasswordResetToken
    from api.models.audit import AuditLog
    from api.models.backup_code import BackupCode
    from api.models.payment import Payment, Subscription

    expected_from_base = set(Base.metadata.tables.keys())

    # Expected tables from ai_coach (different Base, same DB)
    from api.models import ai_coach as ac
    expected_from_ai = set(ac.Base.metadata.tables.keys())

    # rank_alerts_sent is created by migration 004 only (no ORM model)
    expected_extra = {"rank_alerts_sent"}

    expected_tables = expected_from_base | expected_from_ai | expected_extra

    missing_tables = expected_tables - actual_tables
    extra_tables = actual_tables - expected_tables

    issues = []
    if missing_tables:
        issues.append(f"Missing tables: {sorted(missing_tables)}")
    if extra_tables:
        # Rankings/tournament/other feature tables in same DB (intentional)
        extra_known = {
            "alembic_version", "rankings", "ranking_changes", "ranking_history", "ranking_types",
            "org_metadata", "players", "player_statistics", "player_tournament_stats",
            "tournaments", "tournament_definitions", "tournament_history", "tournament_imports",
            "tournament_players", "tournament_results", "tournament_templates",
            "games", "matches", "email_rank_subscriptions",
        }
        unknown_extra = extra_tables - extra_known
        if unknown_extra:
            issues.append(f"Unexpected tables (check if intentional): {sorted(unknown_extra)}")

    # Build expected columns per table from metadata
    def columns_for(table_name):
        if table_name in Base.metadata.tables:
            return {c.name for c in Base.metadata.tables[table_name].c}
        if table_name in ac.Base.metadata.tables:
            return {c.name for c in ac.Base.metadata.tables[table_name].c}
        if table_name == "rank_alerts_sent":
            return {"id", "user_id", "org_code", "player_name", "rank_old", "rank_new", "sent_at", "email"}
        return set()

    for table in sorted(actual_tables):
        if table in ("alembic_version",):
            continue
        actual_cols = {c["name"] for c in inspector.get_columns(table)}
        expected_cols = columns_for(table)
        if not expected_cols:
            continue
        missing_cols = expected_cols - actual_cols
        if missing_cols:
            issues.append(f"Table '{table}' missing columns: {sorted(missing_cols)}")

    # Report (app uses database package: Postgres only)
    db_url = os.environ.get("DATABASE_URL", "postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot")
    print("=== Rankings Bot DB schema verification ===")
    print(f"Database: {db_url}")
    print(f"Actual tables: {len(actual_tables)}")
    print()

    if not issues:
        print("OK: Schema matches expected (all tables and columns present).")
        return 0

    print("ISSUES:")
    for i in issues:
        print(f"  - {i}")
    print()
    print("Fix: Run pending Alembic migrations from project root:")
    print("  source venv/bin/activate && alembic upgrade head")
    print("See docs/DATABASE_CONFIG.md for DB and DATABASE_URL.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
