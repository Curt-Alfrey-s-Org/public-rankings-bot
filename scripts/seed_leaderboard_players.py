#!/usr/bin/env python3
"""
Seed the player leaderboard with a few active players so the Leaderboard UI
shows real rows when the database would otherwise be empty.

Players appear on the leaderboard when they exist in `players` with
membership_status = 'active'. Rank/order is by current_rank, then total_points
(updated by Recalculate rankings from completed tournaments).

Usage:
  DATABASE_URL=postgresql://... python scripts/seed_leaderboard_players.py
  python scripts/seed_leaderboard_players.py --dry-run   # show what would be inserted
"""

from __future__ import annotations

import argparse
import os
import sys

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("psycopg2 required: pip install psycopg2-binary")
    sys.exit(1)

DEFAULT_DB = "postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot"

# Example players: active, with rank and points so they appear in order on the leaderboard
SEED_PLAYERS = [
    {"player_id": "SEED-001", "first_name": "Player", "last_name": "One",   "current_rank": 1, "total_points": 450.0, "total_tournaments_played": 12, "fargo_score": 720},
    {"player_id": "SEED-002", "first_name": "Player", "last_name": "Two",   "current_rank": 2, "total_points": 380.0, "total_tournaments_played": 10, "fargo_score": 698},
    {"player_id": "SEED-003", "first_name": "Player", "last_name": "Three", "current_rank": 3, "total_points": 320.0, "total_tournaments_played":  9, "fargo_score": 675},
    {"player_id": "SEED-004", "first_name": "Player", "last_name": "Four",  "current_rank": 4, "total_points": 290.0, "total_tournaments_played":  8, "fargo_score": 662},
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed leaderboard with example active players.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without writing")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL", DEFAULT_DB)
    if args.dry_run:
        print("Dry run: would insert or update these players for the leaderboard:")
        for p in SEED_PLAYERS:
            print(f"  #{p['current_rank']} {p['first_name']} {p['last_name']} (id={p['player_id']}, pts={p['total_points']})")
        return 0

    conn = None
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        cursor = conn.cursor()

        for p in SEED_PLAYERS:
            cursor.execute(
                """
                INSERT INTO players (
                    player_id, first_name, last_name, membership_status,
                    current_rank, total_points, total_tournaments_played, fargo_score
                ) VALUES (
                    %(player_id)s, %(first_name)s, %(last_name)s, 'active',
                    %(current_rank)s, %(total_points)s, %(total_tournaments_played)s, %(fargo_score)s
                )
                ON CONFLICT (player_id) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    membership_status = 'active',
                    current_rank = EXCLUDED.current_rank,
                    total_points = EXCLUDED.total_points,
                    total_tournaments_played = EXCLUDED.total_tournaments_played,
                    fargo_score = EXCLUDED.fargo_score,
                    updated_at = CURRENT_TIMESTAMP
                """,
                {
                    "player_id": p["player_id"],
                    "first_name": p["first_name"],
                    "last_name": p["last_name"],
                    "current_rank": p["current_rank"],
                    "total_points": p["total_points"],
                    "total_tournaments_played": p["total_tournaments_played"],
                    "fargo_score": p["fargo_score"],
                },
            )
            cursor.execute(
                """
                INSERT INTO player_statistics (player_id)
                VALUES (%s)
                ON CONFLICT (player_id) DO NOTHING
                """,
                (p["player_id"],),
            )

        conn.commit()
        print(f"Seeded {len(SEED_PLAYERS)} players for the leaderboard. Open the Leaderboard page to see them.")
        return 0
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
