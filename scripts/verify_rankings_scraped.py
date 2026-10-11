#!/usr/bin/env python3
"""
Verify that WPA Men, WPA Women, Men's Heyball, and Women's Heyball rankings
were scraped recently (e.g. within the last 20 minutes).
Uses DATABASE_URL from environment or .env. Run from project root.
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# Load .env
_env_file = PROJECT_ROOT / ".env"
if _env_file.exists():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip("'\"").strip()
                if k and v and k not in os.environ:
                    os.environ.setdefault(k, v)

# Rewrite Docker host for local runs
import re
_url = os.environ.get("DATABASE_URL", "")
if _url and "postgres" in _url:
    os.environ["DATABASE_URL"] = re.sub(r"@postgres([:/])", r"@127.0.0.1\1", _url)

SYSTEMS = ("WPA_Men", "WPA_Women", "WPA_Heyball_Men", "WPA_Heyball_Women")
WINDOW_MINUTES = int(os.environ.get("RANKINGS_VERIFY_MINUTES", "20"), 10)


def main() -> int:
    try:
        from database import get_database_manager
        from sqlalchemy import text
    except ImportError as e:
        print("Error: could not import database:", e, file=sys.stderr)
        return 1

    db = get_database_manager()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MINUTES)

    print(f"Checking if rankings were scraped within the last {WINDOW_MINUTES} minutes")
    print(f"Cutoff (UTC): {cutoff.isoformat()}")
    print()

    all_ok = True
    with db.engine.connect() as conn:
        for system in SYSTEMS:
            row = conn.execute(
                text("""
                    SELECT
                        COUNT(*) AS cnt,
                        MAX(snapshot_date) AS last_snapshot,
                        MAX(created_at) AS last_created_at
                    FROM rankings
                    WHERE ranking_system = :system
                """),
                {"system": system},
            ).fetchone()

            cnt = row[0] or 0
            last_snapshot = row[1]
            last_created = row[2]

            if last_created and last_created.tzinfo is None:
                last_created = last_created.replace(tzinfo=timezone.utc)

            within_window = last_created and last_created >= cutoff if last_created else False
            status = "OK" if (cnt and within_window) else ("STALE" if cnt else "MISSING")
            if status != "OK":
                all_ok = False

            print(f"  {system:22} count={cnt:5}  snapshot={last_snapshot}  last_created={last_created}  [{status}]")

    print()
    if all_ok:
        print("All four systems have data scraped within the window.")
        return 0
    print("Some systems are MISSING or STALE. Run refresh_historical_rankings.py and/or refresh_rankings.py.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
