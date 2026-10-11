#!/usr/bin/env python3
"""
Manual Fargo scrape: fetch Top 100 lists from dashboard.fargorate.com and optionally
look up a player (e.g. Debbie Teichert) from fairmatch-style data (we get her from
the Top 100 World Female list if present).

Data source: https://dashboard.fargorate.com/api/TopListsForWeb
- rankingType=World -> Top 100 World (all)
- rankingType=World&gender=Female -> Top 100 World Women
- rankingType=World&gender=Male -> Top 100 World Men
- rankingType=Country -> Top 100 USA

Usage:
  python scripts/manual_fargo_scrape.py                    # print all lists (JSON)
  python scripts/manual_fargo_scrape.py --player "Debbie Teichert"   # find rating for player
  python scripts/manual_fargo_scrape.py --csv > fargo_top100.csv      # CSV for import
  python scripts/manual_fargo_scrape.py --apply              # fetch and update Postgres (requires DATABASE_URL)

Note: Single-player lookup (e.g. Debbie Teichert) from fairmatch.fargorate.com is not available via a
public API; FairMatch is a Meteor app and returns HTML. Players in the Top 100 World/USA/World Women/Men
lists are covered by this script and by the "Update Fargo Rating" button (dashboard fallback).
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    httpx = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DASHBOARD_BASE = "https://dashboard.fargorate.com/api"
LIST_PARAMS = [
    ("Top 100 World", {"rankingType": "World"}),
    ("Top 100 USA", {"rankingType": "Country"}),
    ("Top 100 World Women", {"rankingType": "World", "gender": "Female"}),
    ("Top 100 World Men", {"rankingType": "World", "gender": "Male"}),
]


def fetch_list(label: str, params: dict) -> list:
    """Fetch one top list from dashboard API. Returns list of dicts with FirstName, LastName, Country, FargoRating."""
    if not httpx:
        print("httpx required: pip install httpx", file=sys.stderr)
        return []
    url = f"{DASHBOARD_BASE}/TopListsForWeb"
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        print(f"Error fetching {label}: {e}", file=sys.stderr)
        return []
    if not isinstance(data, list):
        return []
    return data


def full_name(rec: dict) -> str:
    first = (rec.get("FirstName") or "").strip()
    last = (rec.get("LastName") or "").strip()
    return f"{first} {last}".strip() or "Unknown"


def scrape_all() -> dict:
    """Fetch all four lists. Returns { "list_name": [ { player_name, fargo_rating, country }, ... ], ... }."""
    out = {}
    for label, params in LIST_PARAMS:
        raw = fetch_list(label, params)
        out[label] = [
            {
                "player_name": full_name(r),
                "fargo_rating": float(r.get("FargoRating") or 0),
                "country": (r.get("Country") or "").strip(),
                "id": r.get("Id"),
            }
            for r in raw
        ]
    return out


def merged_ratings_by_name(scraped: dict) -> dict:
    """Return dict player_name -> fargo_rating (highest if in multiple lists)."""
    by_name = {}
    for _list_name, players in scraped.items():
        for p in players:
            name = (p.get("player_name") or "").strip()
            if not name:
                continue
            rating = p.get("fargo_rating")
            if rating is None:
                continue
            if name not in by_name or (by_name[name] or 0) < rating:
                by_name[name] = rating
    return by_name


def find_player(scraped: dict, query: str) -> list:
    """Search for a player by name (case-insensitive partial match). Returns list of matches with list name and rating."""
    query = (query or "").strip().lower()
    if not query:
        return []
    matches = []
    for list_name, players in scraped.items():
        for p in players:
            name = (p.get("player_name") or "").strip()
            if query in name.lower():
                matches.append(
                    {
                        "player_name": name,
                        "fargo_rating": p.get("fargo_rating"),
                        "country": p.get("country"),
                        "list": list_name,
                    }
                )
    return matches


def apply_to_db(dry_run: bool = False) -> int:
    """Fetch lists, merge by name, update rankings table by player_name match. Returns count updated."""
    scraped = scrape_all()
    by_name = merged_ratings_by_name(scraped)
    if not by_name:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    fargo_data = [
        {"player_name": name, "fargo_rating": rating, "updated_at": now}
        for name, rating in by_name.items()
    ]
    if dry_run:
        print(f"Would update {len(fargo_data)} player ratings (dry run)", file=sys.stderr)
        return 0
    from api.services.fargo_client import update_rankings_with_fargo
    from database import get_database_manager

    conn = get_database_manager().get_connection()
    try:
        return update_rankings_with_fargo(conn, fargo_data)
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Manual Fargo scrape (dashboard.fargorate.com)")
    parser.add_argument("--player", type=str, help="Look up a player by name (e.g. Debbie Teichert)")
    parser.add_argument("--csv", action="store_true", help="Output merged list as CSV for import")
    parser.add_argument("--apply", action="store_true", help="Update Postgres rankings with scraped ratings (requires DATABASE_URL)")
    parser.add_argument("--dry-run", action="store_true", help="With --apply: only report what would be updated")
    args = parser.parse_args()

    scraped = scrape_all()
    if not any(scraped.values()):
        print("No data fetched. Check network and dashboard.fargorate.com.", file=sys.stderr)
        return 1

    if args.apply:
        updated = apply_to_db(dry_run=args.dry_run)
        print(f"Updated {updated} rankings with Fargo ratings.")
        return 0

    if args.player:
        matches = find_player(scraped, args.player)
        if not matches:
            print(f"No match for '{args.player}' in Top 100 World/USA/World Women/World Men lists.")
            return 0
        for m in matches:
            print(json.dumps(m, indent=2))
        return 0

    if args.csv:
        by_name = merged_ratings_by_name(scraped)
        print("player_name,fargo_rating")
        for name, rating in sorted(by_name.items(), key=lambda x: -x[1]):
            print(f'"{name}",{rating}')
        return 0

    print(json.dumps(scraped, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
