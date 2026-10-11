#!/usr/bin/env python3
"""
Load per-tournament rankings data into tournament_history and tournament_results.

Reads data/per_tournament_rankings.json (from scrape_per_tournament_rankings.py),
matches tournaments to tournament_history, derives placement from points, and upserts
into tournament_results so the Tournament History page shows placement and points.

Usage:
  python scripts/load_per_tournament_rankings_into_tournaments.py
  python scripts/load_per_tournament_rankings_into_tournaments.py --scrape-first  # Run scraper first if JSON missing
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_database_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).parent.parent / "data" / "per_tournament_rankings.json"

# Map division key to association and year extraction.
# Use "WPA Men" / "WPA Women" (not "WPA") so men and women don't get mashed into one row.
DIVISION_MAP = {
    "wpa_men": ("WPA Men", "Men"),
    "wpa_women": ("WPA Women", "Women"),
    "wpa_heyball": ("WPA Heyball", "Heyball"),
    "wpa_artistic": ("WPA Artistic", "Artistic"),
    "wpba_women": ("WPBA", "Women"),
}


def _slug_tournament_id(name: str, year: int, association: str) -> str:
    """Generate tournament_id slug matching tournament_history_scraper."""
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")[:120]
    return f"{year}_{association}_{slug}" if slug else f"{year}_{association}_event"


def _extract_year_from_name(tournament_name: str) -> int:
    """Extract year from tournament name (e.g. '2025 WPBA ...' -> 2025)."""
    m = re.search(r"\b(20\d{2})\b", tournament_name)
    return int(m.group(1)) if m else 0


def _find_or_create_tournament(
    conn, cursor, tournament_name: str, association: str, year: int
) -> str | None:
    """
    Find tournament_history by name/association/year, or create if missing.
    Returns tournament_id or None on error.
    """
    # Normalize for matching
    name_lower = (tournament_name or "").lower().strip()
    if not name_lower:
        return None

    # Try exact match first
    cursor.execute(
        """
        SELECT tournament_id FROM tournament_history
        WHERE LOWER(TRIM(name)) = %s AND association = %s AND (year = %s OR year IS NULL)
        ORDER BY year DESC NULLS LAST
        LIMIT 1
        """,
        (name_lower, association, year if year else None),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    # Try contains match (tournament name might be shortened in rankings)
    pattern = f"%{name_lower[:50]}%"
    cursor.execute(
        """
        SELECT tournament_id, name FROM tournament_history
        WHERE association = %s AND (year = %s OR year IS NULL)
        AND LOWER(name) LIKE %s
        ORDER BY year DESC NULLS LAST
        LIMIT 1
        """,
        (association, year if year else None, pattern),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    # Create new tournament_history entry
    tournament_id = _slug_tournament_id(tournament_name, year or 0, association)
    try:
        cursor.execute(
            """
            INSERT INTO tournament_history (tournament_id, name, year, association, status)
            VALUES (%s, %s, %s, %s, 'completed')
            ON CONFLICT (tournament_id) DO NOTHING
            """,
            (tournament_id, tournament_name[:255], year if year else None, association),
        )
        return tournament_id
    except Exception as e:
        logger.warning("Could not create tournament %s: %s", tournament_id, e)
        return None


def _get_player_stops_played(cursor, player_name: str, tournament_date: str | None) -> int | None:
    """
    Query rankings to get stops_played for a player on or before tournament date.
    Returns stops_played value or None if not found.
    """
    if not tournament_date or not player_name:
        return None
    
    try:
        # Get latest ranking on/before tournament date
        cursor.execute(
            """
            SELECT stops_played FROM rankings
            WHERE player_name = %s
            AND snapshot_date <= %s
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
            (player_name.strip(), tournament_date),
        )
        row = cursor.fetchone()
        if row:
            return int(row[0]) if row[0] is not None else None
    except Exception as e:
        logger.debug("Could not fetch stops_played for %s: %s", player_name, e)
    
    return None


def load_rankings_into_tournaments(
    data_path: Path | None = None,
    scrape_first: bool = False,
) -> dict:
    """
    Load per-tournament rankings JSON into tournament_results.
    Includes stops_played from rankings table if available.
    Returns {tournaments_updated: int, results_upserted: int, errors: int}.
    """
    path = data_path or DATA_PATH
    if scrape_first or not path.exists():
        if not path.exists():
            logger.info("Running scrape_per_tournament_rankings.py first...")
        try:
            from scripts.scrape_per_tournament_rankings import main as scrape_main
            sys.argv = ["scrape_per_tournament_rankings.py", "-o", str(path)]
            scrape_main()
        except Exception as e:
            logger.error("Scrape failed: %s", e)
            return {"tournaments_updated": 0, "results_upserted": 0, "errors": 1}

    if not path.exists():
        logger.error("Per-tournament rankings file not found: %s", path)
        return {"tournaments_updated": 0, "results_upserted": 0, "errors": 1}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    db = get_database_manager()
    conn = db.get_connection()
    cursor = conn.cursor()

    tournaments_updated = 0
    results_upserted = 0
    errors = 0

    try:
        for division_key, division_data in data.items():
            if division_key not in DIVISION_MAP:
                continue
            association, _ = DIVISION_MAP[division_key]
            tournaments = division_data.get("tournaments") or []
            players = division_data.get("players") or []

            for t_idx, tournament_name in enumerate(tournaments):
                if not (tournament_name or "").strip():
                    continue
                year = _extract_year_from_name(tournament_name)
                tournament_id = _find_or_create_tournament(
                    conn, cursor, tournament_name, association, year
                )
                if not tournament_id:
                    errors += 1
                    continue

                # Collect (player_name, points) for this tournament
                player_points = []
                for p in players:
                    tp = p.get("tournament_points") or {}
                    pts = tp.get(tournament_name)
                    if pts is not None and (p.get("name") or "").strip():
                        player_points.append(((p.get("name") or "").strip()[:255], int(pts)))

                if not player_points:
                    continue

                # Sort by points descending -> placement 1, 2, 3, ...
                player_points.sort(key=lambda x: -x[1])
                tournaments_updated += 1
                
                # Get tournament date for stops_played lookup
                cursor.execute(
                    "SELECT date FROM tournament_history WHERE tournament_id = %s",
                    (tournament_id,),
                )
                tournament_date_row = cursor.fetchone()
                tournament_date = tournament_date_row[0] if tournament_date_row else None

                for placement, (player_name, points) in enumerate(player_points, 1):
                    try:
                        # Get stops_played from rankings table
                        stops_played = _get_player_stops_played(cursor, player_name, tournament_date)
                        
                        cursor.execute(
                            """
                            INSERT INTO tournament_results (tournament_id, player_name, placement, points, stops_played)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (tournament_id, player_name) DO UPDATE SET
                                placement = EXCLUDED.placement,
                                points = EXCLUDED.points,
                                stops_played = EXCLUDED.stops_played
                            """,
                            (tournament_id, player_name, placement, float(points), stops_played),
                        )
                        results_upserted += 1
                    except Exception as e:
                        logger.debug("Upsert %s: %s", player_name, e)
                        errors += 1

        conn.commit()

        # Refresh materialized view
        try:
            db.refresh_materialized_views()
        except Exception as e:
            logger.warning("Could not refresh mv_tournament_history_recent: %s", e)

    except Exception as e:
        logger.error("Load failed: %s", e, exc_info=True)
        conn.rollback()
        errors += 1
    finally:
        conn.close()

    return {
        "tournaments_updated": tournaments_updated,
        "results_upserted": results_upserted,
        "errors": errors,
    }


def main():
    ap = argparse.ArgumentParser(description="Load per-tournament rankings into tournament_results")
    ap.add_argument("--scrape-first", action="store_true", help="Run scrape_per_tournament_rankings.py first")
    ap.add_argument("--data-path", type=Path, default=None, help="Path to per_tournament_rankings.json")
    args = ap.parse_args()

    result = load_rankings_into_tournaments(
        data_path=args.data_path,
        scrape_first=args.scrape_first,
    )
    logger.info(
        "Done: %d tournaments updated, %d results upserted, %d errors",
        result["tournaments_updated"],
        result["results_upserted"],
        result["errors"],
    )
    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
