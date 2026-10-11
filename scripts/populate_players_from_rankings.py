#!/usr/bin/env python3
"""Populate players and player_statistics from rankings (DB-only, no scraping)."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from typing import Dict, Iterable, Tuple

import psycopg2
import psycopg2.extras

DEFAULT_DB = "postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot"


def _normalize_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    return cleaned


def _parse_name(name: str) -> Tuple[str, str]:
    name = _normalize_name(name)
    if not name:
        return "Unknown", "Unknown"
    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        last = parts[0] or "Unknown"
        first = parts[1] if len(parts) > 1 and parts[1] else "Unknown"
        return first, last
    parts = name.split()
    if len(parts) == 1:
        return parts[0], "Unknown"
    return parts[0], " ".join(parts[1:])


def _sanitize_id(value: str, max_len: int = 24) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", (value or "").strip())
    cleaned = cleaned.strip("-")
    return cleaned[:max_len] if cleaned else "UNKNOWN"


def _player_id_from_row(name: str, license_number: str | None) -> str:
    # player_id column is VARCHAR(32); keep ids deterministic and within limit.
    if license_number:
        return f"LIC-{_sanitize_id(license_number, 28)}"
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:26]
    return f"RANK-{digest}"


def _latest_rankings_rows(cursor, ranking_system: str | None) -> Iterable[Dict]:
    if ranking_system:
        cursor.execute(
            """
            SELECT player_name, country, license_number, fargo_rating, rank, points, ranking_system
            FROM rankings r
            WHERE r.ranking_system = %s
              AND r.snapshot_date = (
                SELECT MAX(r2.snapshot_date) FROM rankings r2 WHERE r2.ranking_system = r.ranking_system
              )
            """,
            (ranking_system,),
        )
    else:
        cursor.execute(
            """
            SELECT player_name, country, license_number, fargo_rating, rank, points, ranking_system
            FROM rankings r
            WHERE r.snapshot_date = (
                SELECT MAX(r2.snapshot_date) FROM rankings r2 WHERE r2.ranking_system = r.ranking_system
            )
            """
        )
    for row in cursor.fetchall():
        yield dict(row)


def _dedupe_rows(rows: Iterable[Dict]) -> Dict[str, Dict]:
    result: Dict[str, Dict] = {}
    for row in rows:
        name = _normalize_name(row.get("player_name", ""))
        license_number = (row.get("license_number") or "").strip()
        key = license_number.lower() if license_number else name.lower()
        if not key:
            continue
        existing = result.get(key)
        if not existing:
            result[key] = row
            continue
        # Prefer lower rank (better) or higher points
        existing_rank = existing.get("rank")
        row_rank = row.get("rank")
        if row_rank is not None and (existing_rank is None or row_rank < existing_rank):
            result[key] = row
            continue
        existing_points = existing.get("points") or 0
        row_points = row.get("points") or 0
        if row_points > existing_points:
            result[key] = row
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate players and player_statistics from rankings (DB-only).")
    parser.add_argument("--ranking-system", default=None, help="Limit to a ranking_system (e.g., WPBA_Women)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be inserted without writing")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows processed")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL", DEFAULT_DB)
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            rows = list(_latest_rankings_rows(cursor, args.ranking_system))
            deduped = list(_dedupe_rows(rows).values())
            if args.limit:
                deduped = deduped[: args.limit]

            payload = []
            for row in deduped:
                name = _normalize_name(row.get("player_name", ""))
                if not name:
                    continue
                first_name, last_name = _parse_name(name)
                license_number = (row.get("license_number") or "").strip() or None
                player_id = _player_id_from_row(name, license_number)
                country = (row.get("country") or "").strip() or None
                fargo = row.get("fargo_rating")
                fargo_score = int(round(float(fargo))) if fargo is not None else None
                payload.append(
                    {
                        "player_id": player_id,
                        "first_name": first_name,
                        "last_name": last_name,
                        "license_number": license_number,  # Never fabricate; use None when missing
                        "fargo_score": fargo_score,
                        "nationality": country,
                        "membership_status": "active",
                        "total_points": row.get("points") or 0,
                        "current_rank": None,  # Per-system rank not used; global rank from recalculate_rankings
                    }
                )

            if args.dry_run:
                print(f"Would upsert {len(payload)} players")
                return 0

            insert_sql = """
                INSERT INTO players (
                    player_id, first_name, last_name, license_number, fargo_score,
                    nationality, membership_status, total_points, current_rank
                ) VALUES (
                    %(player_id)s, %(first_name)s, %(last_name)s, %(license_number)s, %(fargo_score)s,
                    %(nationality)s, %(membership_status)s, %(total_points)s, %(current_rank)s
                )
                ON CONFLICT (player_id) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    license_number = COALESCE(EXCLUDED.license_number, players.license_number),
                    fargo_score = COALESCE(EXCLUDED.fargo_score, players.fargo_score),
                    nationality = COALESCE(EXCLUDED.nationality, players.nationality),
                    membership_status = COALESCE(EXCLUDED.membership_status, players.membership_status),
                    total_points = COALESCE(EXCLUDED.total_points, players.total_points),
                    current_rank = COALESCE(EXCLUDED.current_rank, players.current_rank),
                    updated_at = CURRENT_TIMESTAMP
            """
            psycopg2.extras.execute_batch(cursor, insert_sql, payload, page_size=500)

            stats_sql = """
                INSERT INTO player_statistics (player_id)
                VALUES (%s)
                ON CONFLICT (player_id) DO NOTHING
            """
            psycopg2.extras.execute_batch(
                cursor,
                stats_sql,
                [(row["player_id"],) for row in payload],
                page_size=500,
            )

            # Populate basic stats from tournament_results (DB-only)
            cursor.execute(
                """
                WITH player_name_map AS (
                    SELECT
                        player_id,
                        LOWER(TRIM(first_name || ' ' || last_name)) AS full_name,
                        LOWER(TRIM(last_name || ', ' || first_name)) AS alt_name
                    FROM players
                ),
                stats AS (
                    SELECT
                        m.player_id,
                        COUNT(DISTINCT tr.tournament_id) AS total_tournaments,
                        SUM(CASE WHEN tr.placement = 1 THEN 1 ELSE 0 END) AS first_place_finishes,
                        SUM(CASE WHEN tr.placement = 2 THEN 1 ELSE 0 END) AS second_place_finishes,
                        SUM(CASE WHEN tr.placement = 3 THEN 1 ELSE 0 END) AS third_place_finishes,
                        AVG(tr.placement::float) AS average_placement,
                        MIN(tr.placement) AS best_placement
                    FROM tournament_results tr
                    JOIN player_name_map m
                      ON LOWER(TRIM(tr.player_name)) IN (m.full_name, m.alt_name)
                    GROUP BY m.player_id
                )
                UPDATE player_statistics ps
                SET
                    total_tournaments = stats.total_tournaments,
                    first_place_finishes = stats.first_place_finishes,
                    second_place_finishes = stats.second_place_finishes,
                    third_place_finishes = stats.third_place_finishes,
                    average_placement = stats.average_placement,
                    best_placement = stats.best_placement,
                    updated_at = CURRENT_TIMESTAMP
                FROM stats
                WHERE ps.player_id = stats.player_id
                """
            )

            cursor.execute(
                """
                WITH player_name_map AS (
                    SELECT
                        player_id,
                        LOWER(TRIM(first_name || ' ' || last_name)) AS full_name,
                        LOWER(TRIM(last_name || ', ' || first_name)) AS alt_name
                    FROM players
                ),
                stats AS (
                    SELECT
                        m.player_id,
                        COUNT(DISTINCT tr.tournament_id) AS total_tournaments
                    FROM tournament_results tr
                    JOIN player_name_map m
                      ON LOWER(TRIM(tr.player_name)) IN (m.full_name, m.alt_name)
                    GROUP BY m.player_id
                )
                UPDATE players p
                SET
                    total_tournaments_played = stats.total_tournaments,
                    updated_at = CURRENT_TIMESTAMP
                FROM stats
                WHERE p.player_id = stats.player_id
                """
            )

            conn.commit()
            print(f"Upserted {len(payload)} players and populated basic stats.")
            return 0
    except Exception as exc:
        conn.rollback()
        print(f"Error: {exc}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
