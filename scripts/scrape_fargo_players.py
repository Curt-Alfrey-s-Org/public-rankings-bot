#!/usr/bin/env python3
"""
Scrape Fargo ratings for one or more players via FairMatch, update DB, and verify.
Uses the same Fargo/FairMatch scraper code as the API sync.

Usage:
  python3 scripts/scrape_fargo_players.py Kennedy Meyman Janet Atwell
  python3 scripts/scrape_fargo_players.py --names "Kennedy Meyman,Janet Atwell"
  python3 scripts/scrape_fargo_players.py --all --org WPBA --verify  # Scrape ALL players for WPBA
  python3 scripts/scrape_fargo_players.py Kennedy Meyman --dry-run   # Scrape only, no DB update
  python3 scripts/scrape_fargo_players.py Kennedy Meyman Janet Atwell --verify  # Update + verify

Run from Rankings-Bot project root. Requires Chrome/Chromium for FairMatch.
Set DATABASE_URL. Docker: postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot (see docs/DOCKER_POSTGRES_ONLY.md).

To analyze with logs: tail -f logs/rankings-api.log in one terminal, run this script in another.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _get_player_rows(conn, player_names: list[str]) -> dict[str, list[dict]]:
    """Return current rankings rows for given player names (latest snapshot per system)."""
    cur = conn.cursor()
    by_name: dict[str, list[dict]] = {}
    for name in player_names:
        cur.execute(
            """SELECT player_name, ranking_system, rank, points, fargo_rating, fargo_last_updated
               FROM rankings r1
               WHERE r1.player_name = %s
               AND r1.snapshot_date = (
                 SELECT MAX(r2.snapshot_date) FROM rankings r2
                 WHERE r2.player_name = r1.player_name AND r2.ranking_system = r1.ranking_system
               )
               ORDER BY r1.ranking_system""",
            (name.strip(),),
        )
        rows = cur.fetchall()
        by_name[name.strip()] = [
            {
                "player_name": r[0],
                "ranking_system": r[1],
                "rank": r[2],
                "points": r[3],
                "fargo_rating": r[4],
                "fargo_last_updated": str(r[5]) if r[5] else None,
            }
            for r in rows
        ] if rows else []
    return by_name


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape Fargo for players via FairMatch, update DB, verify."
    )
    parser.add_argument(
        "players",
        nargs="*",
        help="Player names (e.g. Kennedy Meyman Janet Atwell)",
    )
    parser.add_argument(
        "--names",
        type=str,
        help="Comma-separated player names (alternative to positional)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape only; do not update DB",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="After update, re-query DB and compare (implies not dry-run)",
    )
    parser.add_argument(
        "--source",
        default="fairmatch",
        choices=["fairmatch", "api", "auto"],
        help="Lookup source (default: fairmatch)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scrape ALL players from rankings for --org (use with --org WPBA or WPA)",
    )
    parser.add_argument(
        "--org",
        default="WPBA",
        help="Org code when using --all (WPBA or WPA)",
    )
    args = parser.parse_args()

    names: list[str] = []
    if args.all:
        from database import get_database_manager
        from api.services import fargo_client as fc
        conn = get_database_manager().get_connection()
        names = fc.get_distinct_player_names(conn, args.org)
        conn.close()
        if not names:
            logger.error("No players found for org %s", args.org)
            return 1
        logger.info("--all: %d players from %s", len(names), args.org)
    if args.names:
        names.extend([n.strip() for n in args.names.split(",") if n.strip()])
    if args.players:
        names.extend(args.players)
    if not names:
        parser.error("Provide at least one player name (positional or --names) or use --all --org WPBA")
    names = list(dict.fromkeys(names))  # dedupe, preserve order

    logger.info("Players to scrape: %s", names)

    # Import here so script fails fast if deps missing
    from database import get_database_manager
    from api.services import fargo_client

    conn = get_database_manager().get_connection()

    # Before state
    before = _get_player_rows(conn, names)
    for name in names:
        rows = before.get(name, [])
        if not rows:
            logger.warning("Player '%s' not found in rankings (no rows). Will still attempt scrape.", name)
        else:
            for r in rows:
                logger.info(
                    "BEFORE %s [%s]: rank=%s points=%s fargo=%s last_updated=%s",
                    r["player_name"], r["ranking_system"],
                    r["rank"], r["points"], r["fargo_rating"], r["fargo_last_updated"],
                )

    # Scrape each player
    results: list[dict] = []
    failed: list[str] = []
    for name in names:
        logger.info("Scraping Fargo for: %s", name)
        if args.source == "fairmatch":
            row, err = fargo_client.fetch_one_fargo_rating_fairmatch(name)
        elif args.source == "api":
            row, err = fargo_client.fetch_one_fargo_rating(name, "WPBA")
        else:
            row, err = fargo_client.fetch_one_fargo_rating(name, "WPBA")
            if not row and not err and fargo_client.USE_FAIRMATCH_SCRAPE:
                row, err = fargo_client.fetch_one_fargo_rating_fairmatch(name)

        if err:
            logger.error("  %s: %s", name, err)
            failed.append(name)
            continue
        if not row:
            logger.warning("  %s: No rating found", name)
            failed.append(name)
            continue
        logger.info("  %s: fargo_rating=%s", name, row.get("fargo_rating"))
        results.append(row)

    if failed and not args.dry_run:
        try:
            from api.services.admin_messages import add_fargo_failed
            add_fargo_failed(args.org if args.all else "WPBA", failed, "Script scrape failed")
        except Exception as e:
            logger.warning("Could not add failed to admin messages: %s", e)

    if not results:
        logger.error("No ratings scraped. Check Chrome/Chromium and FairMatch availability.")
        conn.close()
        return 1

    # Update DB unless dry-run
    if args.dry_run:
        logger.info("DRY-RUN: Would update %d players. Skipping DB write.", len(results))
        for r in results:
            print(json.dumps(r, indent=2))
        conn.close()
        return 0

    n = fargo_client.update_rankings_with_fargo(conn, results)
    logger.info("Updated %d rankings rows with Fargo ratings", n)

    # Verify: re-query and compare
    if args.verify or n > 0:
        after = _get_player_rows(conn, [r["player_name"] for r in results])
        logger.info("--- Verification ---")
        for r in results:
            pname = r["player_name"]
            expected = r.get("fargo_rating")
            rows = after.get(pname, [])
            for row in rows:
                actual = row.get("fargo_rating")
                ok = "OK" if actual == expected else "MISMATCH"
                logger.info(
                    "AFTER %s [%s]: fargo=%s (expected %s) %s",
                    pname, row["ranking_system"], actual, expected, ok,
                )

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
