#!/usr/bin/env python3
"""
Enrich the players SSOT with Fargo data from Digital Pool (fill-only).

Phase 3d of docs/MULTI_SOURCE_DATA_INTEGRATION_PLAN.md. Digital Pool's `players`
table carries authoritative Fargo data (fargo_rating, fargo_robustness, country).
Our DP-sourced `rankings` rows already store the Digital Pool `player_id` in
`source_data` and a player_name that originates from Digital Pool.

This job:
  1. Seeds `players.digitalpool_player_id` (Alembic 058) by **unambiguous exact
     canonical full-name** equality: only names that map to exactly one DP id AND
     to exactly one of our player rows are linked (no fuzzy/ambiguous identity,
     per the workspace no-fuzzy-match rule). Fill-only (never re-links).
  2. Fetches the linked DP profiles in batches (GraphQL `id _in`).
  3. Fills `players.fargo_score`, `fargo_robustness`, `nationality`,
     `fargo_last_updated` with COALESCE only — existing values are never
     overridden, so the country-lock policy is respected.

Operator-triggered only (no scheduler).

Prereq for --save: Alembic 058 applied + DB env configured.

Usage:
  python scripts/enrich_players_fargo_from_digitalpool.py            # dry-run report
  python scripts/enrich_players_fargo_from_digitalpool.py --save     # link + enrich
  python scripts/enrich_players_fargo_from_digitalpool.py --save --limit 50
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError as e:
    logger.debug("python-dotenv not available; proceeding without .env autoload: %s", e)

from sqlalchemy import text  # noqa: E402

from scrapers.externalpool_scraper import CpScraper  # noqa: E402

# Link only names that map to exactly one DP id and exactly one of our players.
_LINK_SQL = text("""
WITH name_dp AS (
    SELECT lower(trim(player_name)) AS nm,
           min((source_data->>'digitalpool_player_id')::bigint) AS dpid
    FROM rankings
    WHERE source_data ? 'digitalpool_player_id'
      AND (source_data->>'digitalpool_player_id') ~ '^[0-9]+$'
    GROUP BY 1
    HAVING count(distinct (source_data->>'digitalpool_player_id')) = 1
),
player_name AS (
    SELECT id,
           lower(trim(coalesce(first_name,'') || ' ' || coalesce(last_name,''))) AS nm,
           count(*) OVER (
               PARTITION BY lower(trim(coalesce(first_name,'') || ' ' || coalesce(last_name,'')))
           ) AS cnt
    FROM players
)
UPDATE players p
SET digitalpool_player_id = nd.dpid
FROM name_dp nd, player_name pn
WHERE pn.id = p.id
  AND pn.cnt = 1
  AND pn.nm = nd.nm
  AND p.digitalpool_player_id IS NULL
""")

_FILL_SQL = text("""
UPDATE players
SET fargo_score      = COALESCE(fargo_score, :fargo_rating),
    fargo_robustness = COALESCE(fargo_robustness, :fargo_robustness),
    nationality      = COALESCE(nationality, :country),
    fargo_last_updated = CASE
        WHEN fargo_score IS NULL AND :fargo_rating IS NOT NULL THEN :now
        ELSE fargo_last_updated END
WHERE digitalpool_player_id = :dpid
""")


def main() -> int:
    ap = argparse.ArgumentParser(description="Enrich players with Digital Pool Fargo data (fill-only)")
    ap.add_argument("--save", action="store_true", help="Write linkage + Fargo fills (default: dry-run)")
    ap.add_argument("--limit", type=int, default=None, help="Cap number of DP profiles fetched (testing)")
    ap.add_argument("--batch-size", type=int, default=100, help="GraphQL id _in batch size")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    from database import get_database_manager
    db = get_database_manager()
    engine = db.engine

    # Step 1: link external id (unambiguous exact name) — only on --save.
    if args.save:
        with engine.begin() as conn:
            res = conn.execute(_LINK_SQL)
            linked = res.rowcount or 0
        print(f"Linked players.digitalpool_player_id (new): {linked}")
    else:
        with engine.connect() as conn:
            would = conn.execute(text("""
                WITH name_dp AS (
                    SELECT lower(trim(player_name)) AS nm
                    FROM rankings
                    WHERE source_data ? 'digitalpool_player_id'
                      AND (source_data->>'digitalpool_player_id') ~ '^[0-9]+$'
                    GROUP BY 1
                    HAVING count(distinct (source_data->>'digitalpool_player_id')) = 1
                ),
                player_name AS (
                    SELECT id, lower(trim(coalesce(first_name,'')||' '||coalesce(last_name,''))) AS nm,
                           count(*) OVER (PARTITION BY lower(trim(coalesce(first_name,'')||' '||coalesce(last_name,'')))) AS cnt
                    FROM players
                )
                SELECT count(*) FROM players p
                JOIN player_name pn ON pn.id=p.id AND pn.cnt=1
                JOIN name_dp nd ON nd.nm=pn.nm
                WHERE p.digitalpool_player_id IS NULL
            """)).scalar()
        print(f"[dry-run] Would link {would} players by unambiguous exact name (re-run with --save).")

    # Step 2: collect linked DP ids that still miss fargo_score (or nationality).
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT digitalpool_player_id
            FROM players
            WHERE digitalpool_player_id IS NOT NULL
              AND (fargo_score IS NULL OR nationality IS NULL)
        """)).fetchall()
    dp_ids = [int(r[0]) for r in rows if r[0] is not None]
    if args.limit:
        dp_ids = dp_ids[:args.limit]
    print(f"Linked players needing Fargo/country fill: {len(dp_ids)}")

    if not dp_ids:
        print("Nothing to enrich.")
        return 0

    if not args.save:
        print("[dry-run] Would fetch DP profiles and fill fargo_score/robustness/nationality (COALESCE).")
        return 0

    # Step 3: fetch profiles + fill.
    scraper = CpScraper()
    profiles = scraper.fetch_players_by_ids(dp_ids, batch_size=args.batch_size)
    print(f"Fetched {len(profiles)} DP profiles.")

    now = datetime.now(timezone.utc)
    filled = 0
    with engine.begin() as conn:
        for dpid, prof in profiles.items():
            fr = prof.get("fargo_rating")
            conn.execute(_FILL_SQL, {
                "dpid": dpid,
                "fargo_rating": float(fr) if fr is not None else None,
                "fargo_robustness": prof.get("fargo_robustness"),
                "country": prof.get("country"),
                "now": now,
            })
            filled += 1

    with engine.connect() as conn:
        miss_after = conn.execute(text("SELECT count(*) FROM players WHERE fargo_score IS NULL")).scalar()
        with_fargo = conn.execute(text("SELECT count(*) FROM players WHERE fargo_score IS NOT NULL")).scalar()
    print(f"Applied fill to {filled} linked players. players with fargo_score now: {with_fargo}; still missing: {miss_after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
