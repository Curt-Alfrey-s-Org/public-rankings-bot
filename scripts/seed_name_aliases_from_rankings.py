#!/usr/bin/env python3
"""
Seed player_name_aliases from latest rankings snapshots.

Creates aliases for rows in "Last, First" form:
  scraped_name   = "Last, First"
  canonical_name = "First Last"

This helps Fargo/manual imports resolve formatting differences.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, List, Tuple

import psycopg2


def _connect():
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL is required")
    return psycopg2.connect(db_url)


def _to_canonical(name: str) -> str:
    raw = (name or "").strip()
    if "," not in raw:
        return raw
    parts = [p.strip() for p in raw.split(",", 1)]
    if len(parts) == 2 and parts[0] and parts[1]:
        return f"{parts[1]} {parts[0]}".strip()
    return raw


def _iter_latest_names(cur, systems: Iterable[str]) -> List[Tuple[str, str]]:
    result: List[Tuple[str, str]] = []
    for system in systems:
        cur.execute(
            """
            SELECT player_name
            FROM rankings
            WHERE ranking_system = %s
              AND snapshot_date = (
                SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = %s
              )
            """,
            (system, system),
        )
        for (player_name,) in cur.fetchall():
            if player_name:
                result.append((system, player_name))
    return result


def _swap_last_token_first(name: str) -> str:
    tokens = [t for t in (name or "").split() if t]
    if len(tokens) < 2:
        return (name or "").strip()
    return " ".join([tokens[-1], *tokens[:-1]])


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed player_name_aliases using latest rankings snapshots.")
    parser.add_argument(
        "--systems",
        nargs="*",
        default=["WPA_Men", "WPA_Women", "WPBA_Women"],
        help="Ranking systems to scan.",
    )
    parser.add_argument("--apply", action="store_true", help="Write aliases. Without this flag, dry-run only.")
    args = parser.parse_args()

    conn = _connect()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            rows = _iter_latest_names(cur, args.systems)
            cur.execute(
                """
                SELECT LOWER(TRIM(first_name || ' ' || last_name))
                FROM players
                WHERE fargo_score IS NOT NULL
                GROUP BY LOWER(TRIM(first_name || ' ' || last_name))
                """
            )
            player_names_with_fargo = {r[0] for r in cur.fetchall()}

            inserts: List[Tuple[str, str, str]] = []
            for system, scraped_name in rows:
                canonical_name = ""
                if "," in scraped_name:
                    canonical_name = _to_canonical(scraped_name)
                else:
                    swapped = _swap_last_token_first(scraped_name)
                    if swapped and swapped.lower() in player_names_with_fargo and swapped != scraped_name:
                        canonical_name = swapped

                if canonical_name and canonical_name != scraped_name:
                    inserts.append((scraped_name, canonical_name, system))

            print(f"Potential aliases found: {len(inserts)}")
            for scraped_name, canonical_name, system in inserts[:20]:
                print(f"[{system}] {scraped_name} -> {canonical_name}")

            if not args.apply:
                conn.rollback()
                print("\nDry run only. Re-run with --apply to write aliases.")
                return 0

            for scraped_name, canonical_name, system in inserts:
                cur.execute(
                    """
                    INSERT INTO player_name_aliases (scraped_name, canonical_name, ranking_system)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (scraped_name, ranking_system)
                    DO UPDATE SET canonical_name = EXCLUDED.canonical_name
                    """,
                    (scraped_name, canonical_name, system),
                )

            conn.commit()
            print(f"Aliases upserted: {len(inserts)}")
            return 0
    except Exception as exc:
        conn.rollback()
        print(f"Failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

