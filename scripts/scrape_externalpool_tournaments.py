#!/usr/bin/env python3
"""
Scrape ExternalPool data for tournaments already in app tournament_history.

Flow:
1) Read local tournament_history rows (newest first)
2) Search ExternalPool events by name/date proximity
3) Pull tournament placements + bracket rows
4) Upsert into tournament_history / tournament_results / tournament_history_matches

Usage:
  python3 scripts/scrape_externalpool_tournaments.py
  python3 scripts/scrape_externalpool_tournaments.py --limit 25
  python3 scripts/scrape_externalpool_tournaments.py --force
  python3 scripts/scrape_externalpool_tournaments.py --min-delay 2.0 --max-delay 4.0

  Single tournament by external pool vendor URL slug (GraphQL; writes tab slices + archive JSON):
  python3 scripts/scrape_externalpool_tournaments.py --slug 2026-wpba-classics-players-championship
  python3 scripts/scrape_externalpool_tournaments.py --slug 2026-wpba-classics-players-championship \\
      --local-tournament-id wpba_evt_123
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.externalpool_tournament_harvester import ExternalPoolTournamentHarvester


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Harvest tournament history enrichment from ExternalPool GraphQL")
    parser.add_argument("--limit", type=int, default=None, help="Process only N local tournaments (newest first)")
    parser.add_argument("--force", action="store_true", help="Process even when an ExternalPool bracket URL already exists")
    parser.add_argument(
        "--skip-if-bracket-exists",
        action="store_true",
        default=True,
        help="Skip rows that already have an ExternalPool bracket URL (default: true)",
    )
    parser.add_argument("--min-delay", type=float, default=1.6, help="Minimum delay between upstream requests")
    parser.add_argument("--max-delay", type=float, default=3.2, help="Maximum delay between upstream requests")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retries per upstream request")
    parser.add_argument("--timeout", type=int, default=25, help="HTTP timeout (seconds)")
    parser.add_argument(
        "--min-score",
        type=float,
        default=None,
        help="Minimum External Pool name/date score to accept a match (default: env EXTERNALPOOL_MATCH_MIN_SCORE or 0.35)",
    )
    parser.add_argument(
        "--search-limit",
        type=int,
        default=None,
        help="Max events returned per GraphQL search query (default: env EXTERNALPOOL_SEARCH_LIMIT or 36)",
    )
    parser.add_argument(
        "--slug",
        type=str,
        default=None,
        help="Harvest one tournament by public tournaments/<slug> path on the vendor site (no fuzzy event search)",
    )
    parser.add_argument(
        "--local-tournament-id",
        type=str,
        default=None,
        dest="local_tournament_id",
        help="With --slug: link to this tournament_history.tournament_id for DB upsert (URLs, results, matches)",
    )
    parser.add_argument(
        "--archive-only",
        action="store_true",
        help="With --slug and --local-tournament-id: write JSON archive only (skip DB updates)",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = parse_args()

    harvester = ExternalPoolTournamentHarvester(
        min_delay_sec=args.min_delay,
        max_delay_sec=args.max_delay,
        max_retries=args.max_retries,
        timeout_sec=args.timeout,
        match_min_score=args.min_score,
        search_limit=args.search_limit,
    )
    if getattr(args, "slug", None):
        update_db = bool(args.local_tournament_id) and not args.archive_only
        result = harvester.harvest_by_slug(
            args.slug,
            local_tournament_id=args.local_tournament_id,
            update_database=update_db,
            force=args.force,
            skip_if_bracket_url_exists=args.skip_if_bracket_exists,
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok") else 1

    stats = harvester.harvest(
        limit=args.limit,
        force=args.force,
        skip_if_bracket_url_exists=args.skip_if_bracket_exists,
    )
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

