#!/usr/bin/env python3
"""
Verify that WPA Men total points = sum of all event columns (math matches imports/scraper).
Run from project root. Use --fix to update stored points to the computed sum.
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

if (PROJECT_ROOT / ".env").exists():
    with open(PROJECT_ROOT / ".env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip("'\"").strip()
                if k and v and k not in os.environ:
                    os.environ.setdefault(k, v)

import re
_url = os.environ.get("DATABASE_URL", "")
if _url and "postgres" in _url:
    os.environ["DATABASE_URL"] = re.sub(r"@postgres([:/])", r"@127.0.0.1\1", _url)


def main() -> int:
    try:
        from database import get_database_manager
    except ImportError as e:
        print("Error: could not import database:", e, file=sys.stderr)
        return 1

    do_fix = "--fix" in sys.argv
    db = get_database_manager()

    print("Verifying WPA Men totals (stored points vs sum of all event columns)...")
    mismatches = db.verify_wpa_men_totals(tolerance=0.01)

    if not mismatches:
        print("OK: All WPA Men rows have stored points = sum of event columns.")
        return 0

    print(f"Found {len(mismatches)} row(s) where stored total != computed sum:")
    for m in mismatches[:20]:
        print(f"  {m['player_name']}: stored={m['stored_points']} computed={m['computed_total']} diff={m['diff']}")
    if len(mismatches) > 20:
        print(f"  ... and {len(mismatches) - 20} more.")

    if do_fix:
        print("Applying fix: updating stored points to computed sum...")
        updated = db.recalculate_wpa_men_totals_from_source_data(tolerance=0.01)
        print(f"Updated {updated} row(s).")
        # Re-verify
        after = db.verify_wpa_men_totals(tolerance=0.01)
        if after:
            print(f"WARNING: {len(after)} mismatches remain.", file=sys.stderr)
            return 1
        print("OK: All rows now match.")
        return 0

    print("Run with --fix to update stored points to the computed sum.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
