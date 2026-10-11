#!/usr/bin/env python3
"""
Rebuild a consistent "current" rankings snapshot from best available source snapshots.

Goal:
- Keep historical snapshots intact.
- Choose a source snapshot per ranking_system using recency + row-count sanity.
- Copy chosen rows into a target snapshot_date (default: today) so APIs/UI have
  one coherent "latest" view.

Selection rule per ranking_system:
- Prefer latest snapshot_date.
- If latest rowcount is below (prev_rowcount * min_ratio), use previous snapshot.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

import psycopg2


@dataclass
class SnapshotDecision:
    ranking_system: str
    latest_date: date
    latest_count: int
    chosen_date: date
    chosen_count: int
    reason: str


def _connect():
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL is required")
    return psycopg2.connect(db_url)


def _discover_systems(cur, systems: Optional[List[str]]) -> List[str]:
    if systems:
        return systems
    cur.execute(
        """
        SELECT DISTINCT ranking_system
        FROM rankings
        ORDER BY ranking_system
        """
    )
    return [r[0] for r in cur.fetchall()]


def _decide_source_snapshot(cur, ranking_system: str, min_ratio: float) -> Optional[SnapshotDecision]:
    cur.execute(
        """
        SELECT snapshot_date, COUNT(*) AS cnt
        FROM rankings
        WHERE ranking_system = %s
        GROUP BY snapshot_date
        ORDER BY snapshot_date DESC
        LIMIT 2
        """,
        (ranking_system,),
    )
    rows = cur.fetchall()
    if not rows:
        return None

    latest_date, latest_count = rows[0][0], int(rows[0][1] or 0)
    chosen_date, chosen_count, reason = latest_date, latest_count, "latest"

    if len(rows) > 1:
        prev_date, prev_count = rows[1][0], int(rows[1][1] or 0)
        if prev_count > 0:
            ratio = latest_count / float(prev_count)
            if ratio < min_ratio:
                chosen_date = prev_date
                chosen_count = prev_count
                reason = f"fallback_prev_ratio={ratio:.3f}<min_ratio={min_ratio:.3f}"

    return SnapshotDecision(
        ranking_system=ranking_system,
        latest_date=latest_date,
        latest_count=latest_count,
        chosen_date=chosen_date,
        chosen_count=chosen_count,
        reason=reason,
    )


def _archive_target_rows(cur, ranking_system: str, target_date: date) -> int:
    cur.execute(
        """
        INSERT INTO rankings_archive (
            original_id, player_name, ranking_system, rank, points, country,
            snapshot_date, license_number, fargo_rating, archive_reason
        )
        SELECT
            r.id, r.player_name, r.ranking_system, r.rank, r.points, r.country,
            r.snapshot_date, r.license_number, r.fargo_rating, 'pre_update'
        FROM rankings r
        WHERE r.ranking_system = %s
          AND r.snapshot_date = %s
        """,
        (ranking_system, target_date),
    )
    return cur.rowcount or 0


def _replace_target_snapshot(cur, ranking_system: str, source_date: date, target_date: date) -> int:
    cur.execute(
        """
        DELETE FROM rankings
        WHERE ranking_system = %s
          AND snapshot_date = %s
        """,
        (ranking_system, target_date),
    )

    cur.execute(
        """
        INSERT INTO rankings (
            player_name, ranking_system, rank, points, country, snapshot_date,
            license_number, fargo_rating, fargo_last_updated, created_at,
            stops_played, alfa_rating, fargo_name_format, fargo_source,
            country_source, license_source, source_data, position, fargo_robustness
        )
        SELECT
            player_name, ranking_system, rank, points, country, %s AS snapshot_date,
            license_number, fargo_rating, fargo_last_updated, NOW(),
            stops_played, alfa_rating, fargo_name_format, fargo_source,
            country_source, license_source, source_data, position, fargo_robustness
        FROM rankings
        WHERE ranking_system = %s
          AND snapshot_date = %s
        ORDER BY position ASC, rank ASC, id ASC
        """,
        (target_date, ranking_system, source_date),
    )
    return cur.rowcount or 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild current snapshots from best available source snapshots.")
    parser.add_argument(
        "--target-date",
        default=str(date.today()),
        help="Target snapshot_date to write (YYYY-MM-DD). Default: today.",
    )
    parser.add_argument(
        "--systems",
        nargs="*",
        default=None,
        help="Optional subset of ranking_system values.",
    )
    parser.add_argument(
        "--min-ratio",
        type=float,
        default=0.70,
        help="Fallback threshold: if latest_count / prev_count < min_ratio, use previous snapshot.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply writes. Without this flag, runs in dry-run mode.",
    )
    args = parser.parse_args()

    target_date = date.fromisoformat(args.target_date)
    min_ratio = max(0.01, min(1.0, args.min_ratio))

    conn = _connect()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            systems = _discover_systems(cur, args.systems)
            decisions: List[SnapshotDecision] = []
            for system in systems:
                d = _decide_source_snapshot(cur, system, min_ratio=min_ratio)
                if d:
                    decisions.append(d)

            print(f"Planned systems: {len(decisions)}")
            print("ranking_system | latest_date/latest_count -> chosen_date/chosen_count | reason")
            for d in decisions:
                print(
                    f"{d.ranking_system} | {d.latest_date}/{d.latest_count} -> "
                    f"{d.chosen_date}/{d.chosen_count} | {d.reason}"
                )

            if not args.apply:
                conn.rollback()
                print("\nDry run only. Re-run with --apply to write.")
                return 0

            archived_total = 0
            inserted_total = 0
            for d in decisions:
                archived_total += _archive_target_rows(cur, d.ranking_system, target_date)
                inserted_total += _replace_target_snapshot(cur, d.ranking_system, d.chosen_date, target_date)

            # Refresh materialized view when present.
            cur.execute("SELECT to_regclass('public.mv_latest_rankings')")
            mv_exists = cur.fetchone()[0] is not None
            if mv_exists:
                cur.execute("REFRESH MATERIALIZED VIEW mv_latest_rankings")

            conn.commit()
            print(
                f"\nApplied successfully: archived={archived_total}, inserted={inserted_total}, "
                f"target_date={target_date}, refreshed_mv={mv_exists}"
            )
            return 0
    except Exception as exc:
        conn.rollback()
        print(f"Failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

