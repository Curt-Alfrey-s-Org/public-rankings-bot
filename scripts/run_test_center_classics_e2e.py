#!/usr/bin/env python3
"""
Run the Classics USA Test Center E2E flow without HTTP auth.

Usage (inside API container):
  docker exec rankings-bot-api python scripts/run_test_center_classics_e2e.py

Optional:
  --no-reset   Skip reset; use current tournament if present (still runs setup insert)
  --scheduled  Prefill from first upcoming_events row (mirrors scheduled picker path)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime

SCRIPT_DIR = __import__("os").path.dirname(__import__("os").path.abspath(__file__))
PROJECT_ROOT = __import__("os").path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.routes.test_tournaments import test_manager  # noqa: E402
from api.services import bracket_engine  # noqa: E402


CLASSICS_SETUP = {
    "name": "The Classics USA",
    "format": "double_elimination",
    "max_players": 64,
    "entry_fee": 1000.0,
    "prize_pool": 20000.0,
    "tables": 14,
    "race_to": 8,
    "race_to_final": 10,
    "location": "Sparta, TN",
    "start_date": "2026-04-15T00:00:00",
    "end_date": "2026-04-17T23:59:59",
    "ranking_system": "WPBA_Women",
    "game_type": "9-ball",
    "association": "WPBA",
    "bracket_draw_size": 64,
    "bye_strategy": "top_seed",
}


def _insert_tournament(data: dict) -> str:
    """Insert tournament row (same fields as POST /api/test-tournaments/setup)."""
    ps = data.get("points_structure") or bracket_engine.wpba_default_points_structure()
    points_json = json.dumps(ps)
    tournament_id = f"test_tournament_{int(time.time())}"
    bracket_draw_size = int(
        data.get("bracket_draw_size") or bracket_engine.next_power_of_two(max(2, data["max_players"]))
    )

    conn = test_manager.db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO test_tournaments
            (tournament_id, name, format, max_players, entry_fee, prize_pool, tables, race_to,
             race_to_final, status, location, start_date, end_date, points_structure, ranking_system,
             game_type, association, bracket_template_id, bracket_draw_size, bye_strategy)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tournament_id,
                data["name"],
                data["format"],
                data["max_players"],
                data["entry_fee"],
                data["prize_pool"],
                data["tables"],
                data["race_to"],
                data["race_to_final"],
                "registration",
                data.get("location") or "Test Venue",
                data.get("start_date") or datetime.now().isoformat(),
                data.get("end_date"),
                points_json,
                data.get("ranking_system"),
                data.get("game_type"),
                data.get("association"),
                data.get("bracket_template_id"),
                bracket_draw_size,
                data.get("bye_strategy") or "top_seed",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return tournament_id


def _prefill_from_upcoming() -> dict | None:
    """Read first upcoming event from production DB (scheduled picker data source)."""
    from database import get_engine
    from sqlalchemy import text

    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, name, location, start_date, end_date, event_date,
                       association, format, prize_pool
                FROM upcoming_events
                WHERE COALESCE(start_date, event_date) >= CURRENT_DATE
                ORDER BY COALESCE(start_date, event_date) ASC
                LIMIT 1
                """
            )
        ).mappings().first()
    if not row:
        return None
    out = dict(CLASSICS_SETUP)
    out["name"] = row.get("name") or out["name"]
    if row.get("location"):
        out["location"] = row["location"]
    sd = row.get("start_date") or row.get("event_date")
    if sd:
        out["start_date"] = str(sd)
    if row.get("end_date"):
        out["end_date"] = str(row["end_date"])
    if row.get("association"):
        out["association"] = row["association"]
    fmt = (row.get("format") or "").lower()
    if "double" in fmt:
        out["format"] = "double_elimination"
    elif "single" in fmt:
        out["format"] = "single_elimination"
    if row.get("prize_pool"):
        digits = "".join(c for c in str(row["prize_pool"]) if c.isdigit())
        if digits:
            out["prize_pool"] = float(digits)
    print(f"Scheduled prefill from upcoming_events id={row['id']}: {out['name']}")
    return out


def simulate_all_remaining(winner_bias: str = "fair") -> int:
    """Same loop as POST /simulate-all-remaining."""
    simulated = 0
    max_iters = 5000
    for _ in range(max_iters):
        matches = test_manager.get_matches()
        playable = []
        for m in matches:
            if m.get("status") != "pending":
                continue
            n1 = (m.get("operator_name") or "").strip()
            n2 = (m.get("player2_name") or "").strip()
            if n1 in ("TBD", "BYE", "") or n2 in ("TBD", "BYE", ""):
                continue
            if not m.get("operator_id") or not m.get("player2_id"):
                continue
            playable.append(m)
        if not playable:
            break
        playable.sort(key=lambda x: bracket_engine.simulation_sort_key(x))
        test_manager.simulate_match(playable[0]["match_id"], winner_bias)
        simulated += 1
    return simulated


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Center Classics USA E2E")
    parser.add_argument("--no-reset", action="store_true", help="Skip reset_all_test_data")
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="Prefill setup from first upcoming_events row instead of Classics preset",
    )
    args = parser.parse_args()

    if not args.no_reset:
        print("1/5 Reset test database…")
        stats = test_manager.reset_all_test_data()
        print(f"   cleared: {stats}")

    setup = _prefill_from_upcoming() if args.scheduled else dict(CLASSICS_SETUP)
    if setup is None:
        print("No upcoming events found; falling back to Classics USA preset.")
        setup = dict(CLASSICS_SETUP)

    print(f"2/5 Setup tournament: {setup['name']} ({setup['format']}, draw {setup['bracket_draw_size']})…")
    tid = _insert_tournament(setup)
    print(f"   tournament_id={tid}")

    print("3/5 Seed 64 classics demo players…")
    n_players = test_manager.seed_classics_demo_players()
    print(f"   registered={n_players}")

    print("4/5 Generate bracket…")
    n_matches = test_manager.generate_bracket()
    expected = 126 if setup["format"] == "double_elimination" and setup["bracket_draw_size"] == 64 else "?"
    print(f"   matches_created={n_matches} (expected {expected} for 64 DE)")

    print("5/5 Simulate all remaining matches…")
    n_sim = simulate_all_remaining()
    print(f"   simulated={n_sim}")

    current = test_manager.get_current_tournament()
    status = (current or {}).get("status", "unknown")
    print(f"\nDone. Tournament status={status!r}, id={tid}")
    if status != "completed":
        pending = sum(
            1
            for m in test_manager.get_matches(tid)
            if m.get("status") == "pending"
        )
        print(f"WARNING: {pending} matches still pending.")
        return 1
    print("E2E flow completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
