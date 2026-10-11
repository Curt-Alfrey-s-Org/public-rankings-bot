#!/usr/bin/env python3
"""
Remove old rankings snapshots to reduce duplicates and free space.
Keeps only the most recent snapshot per ranking_system by default, or last N days.
Run from project root. Requires DATABASE_URL.
Usage:
  python3 scripts/cleanup_old_rankings_snapshots.py           # Keep latest only
  python3 scripts/cleanup_old_rankings_snapshots.py --days 7  # Keep last 7 days
  python3 scripts/cleanup_old_rankings_snapshots.py --dry-run # Preview only
"""

import argparse
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# Load .env
env_path = PROJECT_ROOT / ".env"
if env_path.is_file():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))
url = os.environ.get("DATABASE_URL", "")
if url and "postgres" in url:
    url = re.sub(r"@postgres([:/])", r"@127.0.0.1\1", url)
    os.environ["DATABASE_URL"] = url


def main():
    parser = argparse.ArgumentParser(description="Clean old rankings snapshots")
    parser.add_argument("--days", type=int, default=0, help="Keep snapshots from last N days (0 = keep latest only)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    args = parser.parse_args()

    from database import engine
    from sqlalchemy import text

    with engine.connect() as conn:
        if args.days > 0:
            cutoff = date.today() - timedelta(days=args.days)
            result = conn.execute(text("""
                SELECT ranking_system, snapshot_date, COUNT(*) as cnt
                FROM rankings
                WHERE snapshot_date < :cutoff
                GROUP BY ranking_system, snapshot_date
                ORDER BY ranking_system, snapshot_date
            """), {"cutoff": cutoff.isoformat()})
            rows = result.fetchall()
            total = sum(r[2] for r in rows)
            if not rows:
                print("No snapshots older than {} days. Nothing to delete.".format(args.days))
                return 0
            print("Would delete {} rows from snapshots before {}:".format(total, cutoff))
            for r in rows:
                print("  {} {}: {} rows".format(r[0], r[1], r[2]))
            if not args.dry_run:
                conn.execute(text("""
                    DELETE FROM rankings WHERE snapshot_date < :cutoff
                """), {"cutoff": cutoff.isoformat()})
                conn.commit()
                print("Deleted {} rows.".format(total))
        else:
            # Keep only latest snapshot per system
            result = conn.execute(text("""
                WITH latest AS (
                    SELECT ranking_system, MAX(snapshot_date) as max_date
                    FROM rankings GROUP BY ranking_system
                ),
                to_delete AS (
                    SELECT r.id FROM rankings r
                    JOIN latest l ON r.ranking_system = l.ranking_system AND r.snapshot_date < l.max_date
                )
                SELECT COUNT(*) FROM to_delete
            """))
            count = result.scalar()
            if count == 0:
                print("No old snapshots. Each system has only one snapshot.")
                return 0
            print("Would delete {} rows (keeping latest snapshot per system).".format(count))
            if not args.dry_run:
                conn.execute(text("""
                    WITH latest AS (
                        SELECT ranking_system, MAX(snapshot_date) as max_date
                        FROM rankings GROUP BY ranking_system
                    )
                    DELETE FROM rankings r
                    USING latest l
                    WHERE r.ranking_system = l.ranking_system AND r.snapshot_date < l.max_date
                """))
                conn.commit()
                print("Deleted {} rows.".format(count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
