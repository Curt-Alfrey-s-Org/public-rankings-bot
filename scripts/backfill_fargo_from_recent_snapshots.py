#!/usr/bin/env python3
"""
Backfill players.fargo_score / players.fargo_robustness from recent rankings snapshots.

No external scraping/API calls are performed.
Data source is rankings table only (latest snapshot per ranking_system).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

import psycopg2
import psycopg2.extras


SYSTEMS_CORE = ("WPA_Men", "WPA_Women", "WPBA_Women")


def normalize_spaces(value: str) -> str:
    return " ".join((value or "").split()).strip()


def canonical_name(name: str) -> str:
    raw = normalize_spaces(name)
    if "," in raw:
        parts = [p.strip() for p in raw.split(",", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            raw = f"{parts[1]} {parts[0]}"
    return normalize_spaces(raw)


def swap_last_token(name: str) -> str:
    raw = normalize_spaces(name)
    parts = raw.split(" ")
    if len(parts) < 2:
        return raw
    return normalize_spaces(" ".join([parts[-1], *parts[:-1]]))


def norm_key(name: str) -> str:
    c = canonical_name(name).lower()
    if not c:
        return ""
    ascii_name = unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Fargo from recent rankings snapshots (no scraping)")
    parser.add_argument("--systems", nargs="*", default=list(SYSTEMS_CORE), help="Ranking systems to target")
    parser.add_argument("--all-systems", action="store_true", help="Use latest snapshot for every ranking_system")
    parser.add_argument(
        "--recent-days",
        type=int,
        default=None,
        help="Use all source rows from the last N days instead of only latest snapshot per system.",
    )
    parser.add_argument("--apply", action="store_true", help="Apply updates (default is dry-run)")
    return parser.parse_args()


def load_alias_map(cur) -> Dict[Tuple[str, str], str]:
    cur.execute("SELECT ranking_system, scraped_name, canonical_name FROM player_name_aliases")
    alias_map: Dict[Tuple[str, str], str] = {}
    for ranking_system, scraped_name, canonical in cur.fetchall():
        if not ranking_system or not scraped_name or not canonical:
            continue
        alias_map[(str(ranking_system), str(scraped_name))] = str(canonical)
    return alias_map


def load_latest_snapshot_rows(
    cur,
    systems: Iterable[str],
    all_systems: bool,
    recent_days: Optional[int],
) -> List[Tuple[str, datetime, str, Optional[float], Optional[int]]]:
    if recent_days is not None and recent_days > 0:
        if all_systems:
            cur.execute(
                """
                SELECT
                  r.ranking_system,
                  r.snapshot_date,
                  r.player_name,
                  r.fargo_rating,
                  r.fargo_robustness
                FROM rankings r
                WHERE r.snapshot_date >= (CURRENT_DATE - (%s * INTERVAL '1 day'))
                  AND (r.fargo_rating IS NOT NULL OR r.fargo_robustness IS NOT NULL)
                """,
                (recent_days,),
            )
        else:
            cur.execute(
                """
                SELECT
                  r.ranking_system,
                  r.snapshot_date,
                  r.player_name,
                  r.fargo_rating,
                  r.fargo_robustness
                FROM rankings r
                WHERE r.ranking_system = ANY(%s)
                  AND r.snapshot_date >= (CURRENT_DATE - (%s * INTERVAL '1 day'))
                  AND (r.fargo_rating IS NOT NULL OR r.fargo_robustness IS NOT NULL)
                """,
                (list(systems), recent_days),
            )
        return list(cur.fetchall())

    if all_systems:
        cur.execute(
            """
            WITH latest AS (
              SELECT ranking_system, MAX(snapshot_date) AS snapshot_date
              FROM rankings
              GROUP BY ranking_system
            )
            SELECT
              r.ranking_system,
              r.snapshot_date,
              r.player_name,
              r.fargo_rating,
              r.fargo_robustness
            FROM rankings r
            JOIN latest l
              ON l.ranking_system = r.ranking_system
             AND l.snapshot_date = r.snapshot_date
            WHERE r.fargo_rating IS NOT NULL OR r.fargo_robustness IS NOT NULL
            """
        )
    else:
        cur.execute(
            """
            WITH latest AS (
              SELECT ranking_system, MAX(snapshot_date) AS snapshot_date
              FROM rankings
              WHERE ranking_system = ANY(%s)
              GROUP BY ranking_system
            )
            SELECT
              r.ranking_system,
              r.snapshot_date,
              r.player_name,
              r.fargo_rating,
              r.fargo_robustness
            FROM rankings r
            JOIN latest l
              ON l.ranking_system = r.ranking_system
             AND l.snapshot_date = r.snapshot_date
            WHERE (r.fargo_rating IS NOT NULL OR r.fargo_robustness IS NOT NULL)
            """,
            (list(systems),),
        )
    return list(cur.fetchall())


def pick_better(
    a: Optional[Tuple[datetime, Optional[float], Optional[int], str, str]],
    b: Tuple[datetime, Optional[float], Optional[int], str, str],
) -> Tuple[datetime, Optional[float], Optional[int], str, str]:
    """
    Choose newer source; on tie keep one with more populated values.
    """
    if a is None:
        return b
    if b[0] > a[0]:
        return b
    if b[0] < a[0]:
        return a
    a_score = int(a[1] is not None) + int(a[2] is not None)
    b_score = int(b[1] is not None) + int(b[2] is not None)
    return b if b_score > a_score else a


def build_source_map(
    rows: List[Tuple[str, datetime, str, Optional[float], Optional[int]]],
    alias_map: Dict[Tuple[str, str], str],
) -> Dict[str, Tuple[datetime, Optional[float], Optional[int], str, str]]:
    """
    Build normalized name key -> best source tuple.
    Tuple: (snapshot_date, fargo_rating, robustness, ranking_system, player_name)
    """
    by_key: Dict[str, Tuple[datetime, Optional[float], Optional[int], str, str]] = {}
    for ranking_system, snapshot_date, player_name, fargo_rating, fargo_robustness in rows:
        if not player_name:
            continue
        names = {
            str(player_name),
            canonical_name(str(player_name)),
            swap_last_token(canonical_name(str(player_name))),
        }
        alias = alias_map.get((str(ranking_system), str(player_name)))
        if alias:
            names.add(alias)
            names.add(canonical_name(alias))
            names.add(swap_last_token(canonical_name(alias)))

        src = (snapshot_date, fargo_rating, fargo_robustness, str(ranking_system), str(player_name))
        for n in names:
            key = norm_key(n)
            if not key:
                continue
            by_key[key] = pick_better(by_key.get(key), src)
    return by_key


def load_players(cur):
    cur.execute(
        """
        SELECT id, first_name, last_name, fargo_score, fargo_robustness
        FROM players
        """
    )
    return cur.fetchall()


def main() -> int:
    args = parse_args()
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 1

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            alias_map = load_alias_map(cur)
            source_rows = load_latest_snapshot_rows(cur, args.systems, args.all_systems, args.recent_days)
            source_map = build_source_map(source_rows, alias_map)
            players = load_players(cur)

            updates: List[Dict[str, object]] = []
            now_utc = datetime.now(timezone.utc)
            for player_id, first_name, last_name, fargo_score, fargo_robustness in players:
                full_name = normalize_spaces(f"{first_name or ''} {last_name or ''}")
                candidate_keys = {
                    norm_key(full_name),
                    norm_key(swap_last_token(full_name)),
                }
                source = None
                for key in candidate_keys:
                    if key and key in source_map:
                        source = source_map[key]
                        break
                if source is None:
                    continue

                src_date, src_fargo, src_rob, _src_system, _src_name = source
                need_fargo = fargo_score is None and src_fargo is not None
                need_rob = fargo_robustness is None and src_rob is not None
                if not (need_fargo or need_rob):
                    continue

                updates.append(
                    {
                        "id": player_id,
                        "fargo_score": src_fargo if need_fargo else None,
                        "fargo_robustness": src_rob if need_rob else None,
                        "updated_at": now_utc,
                        "src_date": src_date,
                    }
                )

            mode = (
                f"recent {args.recent_days} days"
                if args.recent_days is not None and args.recent_days > 0
                else "latest snapshot per system"
            )
            print(f"Source mode: {mode}")
            print(f"Source rows considered: {len(source_rows)}")
            print(f"Source name keys built: {len(source_map)}")
            print(f"Players needing fill: {len(updates)}")

            if not args.apply:
                print("Dry-run only. Re-run with --apply to write updates.")
                return 0

            if updates:
                psycopg2.extras.execute_batch(
                    cur,
                    """
                    UPDATE players
                    SET
                      fargo_score = COALESCE(fargo_score, %(fargo_score)s),
                      fargo_robustness = COALESCE(fargo_robustness, %(fargo_robustness)s),
                      fargo_last_updated = COALESCE(fargo_last_updated, %(updated_at)s)
                    WHERE id = %(id)s
                    """,
                    updates,
                    page_size=500,
                )

            # Keep latest ranking rows consistent with player overlay values.
            if args.all_systems:
                cur.execute(
                    """
                    WITH latest AS (
                      SELECT ranking_system, MAX(snapshot_date) AS snapshot_date
                      FROM rankings
                      GROUP BY ranking_system
                    ),
                    players_by_name AS (
                      SELECT
                        LOWER(TRIM(first_name || ' ' || last_name)) AS full_name,
                        MAX(fargo_score) AS fargo_score,
                        MAX(fargo_robustness) AS fargo_robustness
                      FROM players
                      GROUP BY LOWER(TRIM(first_name || ' ' || last_name))
                    ),
                    target_rows AS (
                      SELECT
                        r.id,
                        LOWER(
                          TRIM(
                            CASE
                              WHEN POSITION(',' IN r.player_name) > 0 THEN
                                TRIM(SPLIT_PART(r.player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(r.player_name, ',', 1))
                              ELSE r.player_name
                            END
                          )
                        ) AS direct_name
                      FROM rankings r
                      JOIN latest l
                        ON l.ranking_system = r.ranking_system
                       AND l.snapshot_date = r.snapshot_date
                    )
                    UPDATE rankings r
                    SET
                      fargo_rating = COALESCE(r.fargo_rating, p.fargo_score),
                      fargo_robustness = COALESCE(r.fargo_robustness, p.fargo_robustness)
                    FROM target_rows t
                    LEFT JOIN players_by_name p
                      ON p.full_name = t.direct_name
                    WHERE r.id = t.id
                    """
                )
            else:
                cur.execute(
                    """
                    WITH latest AS (
                      SELECT ranking_system, MAX(snapshot_date) AS snapshot_date
                      FROM rankings
                      WHERE ranking_system = ANY(%s)
                      GROUP BY ranking_system
                    ),
                    players_by_name AS (
                      SELECT
                        LOWER(TRIM(first_name || ' ' || last_name)) AS full_name,
                        MAX(fargo_score) AS fargo_score,
                        MAX(fargo_robustness) AS fargo_robustness
                      FROM players
                      GROUP BY LOWER(TRIM(first_name || ' ' || last_name))
                    ),
                    target_rows AS (
                      SELECT
                        r.id,
                        LOWER(
                          TRIM(
                            CASE
                              WHEN POSITION(',' IN r.player_name) > 0 THEN
                                TRIM(SPLIT_PART(r.player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(r.player_name, ',', 1))
                              ELSE r.player_name
                            END
                          )
                        ) AS direct_name
                      FROM rankings r
                      JOIN latest l
                        ON l.ranking_system = r.ranking_system
                       AND l.snapshot_date = r.snapshot_date
                    )
                    UPDATE rankings r
                    SET
                      fargo_rating = COALESCE(r.fargo_rating, p.fargo_score),
                      fargo_robustness = COALESCE(r.fargo_robustness, p.fargo_robustness)
                    FROM target_rows t
                    LEFT JOIN players_by_name p
                      ON p.full_name = t.direct_name
                    WHERE r.id = t.id
                    """,
                    (list(args.systems),),
                )
            rankings_updated = cur.rowcount or 0

            conn.commit()
            print(f"Updated players rows: {len(updates)}")
            print(f"Updated latest rankings rows (coalesce fill): {rankings_updated}")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())

