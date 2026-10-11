#!/usr/bin/env python3
"""
Seed EST ratings for players with no rating using tournament placement (rankings table).
Run from project root: PYTHONPATH=/path/to/rankings-bot python3 scripts/seed_est_from_placement.py
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from database import get_database_manager
from api.services.live_rating_engine import LiveRatingEngine


def main() -> int:
    print("Starting EST seed from placement (loading DB and player list)...")
    db = get_database_manager()
    engine = LiveRatingEngine(db)
    conn = db.get_connection()
    cursor = conn.cursor()
    # Players with no EST who appear in rankings (by name match)
    cursor.execute("""
        SELECT p.player_id
        FROM players p
        WHERE p.est_rating IS NULL
        AND (
            EXISTS (
                SELECT 1 FROM rankings r
                WHERE r.player_name = TRIM(p.first_name || ' ' || p.last_name)
            )
            OR EXISTS (
                SELECT 1 FROM rankings r
                WHERE r.player_name = TRIM(p.last_name || ', ' || p.first_name)
            )
        )
        ORDER BY p.player_id
    """)
    player_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    seeded = 0
    for pid in player_ids:
        if engine.seed_est_from_tournament_placement(pid) is not None:
            seeded += 1
    print(f"Seeded EST for {seeded} of {len(player_ids)} players with no rating.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
