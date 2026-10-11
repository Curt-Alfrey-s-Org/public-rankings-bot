#!/usr/bin/env python3
"""
Fetch FargoRate Top-pool_opt_in lists from dashboard.fargorate.com, save as recent import file,
and fill as many DB rows as possible (exact + prefix match: e.g. "Margarita" in DB matches
"Margarita Fefilova" in list).

No new scraping beyond the public dashboard API. Creates data/fargo_import_<date>.json
so you have a "recent import" to inspect or re-run.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DASHBOARD_BASE = os.getenv("FARGO_DASHBOARD_URL", "https://dashboard.fargorate.com/api")
LIST_PARAMS = [
    {"rankingType": "World"},
    {"rankingType": "Country"},
    {"rankingType": "World", "gender": "Female"},
    {"rankingType": "World", "gender": "Male"},
]
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def fetch_lists() -> list[dict]:
    """Fetch all TopListsForWeb responses. Returns list of { name, fargo_rating, country?, source }."""
    try:
        import httpx
    except ImportError:
        logger.error("httpx required: pip install httpx")
        return []

    out = []
    with httpx.Client(timeout=30) as client:
        for params in LIST_PARAMS:
            try:
                r = client.get(f"{DASHBOARD_BASE}/TopListsForWeb", params=params, timeout=15)
                if r.status_code != 200:
                    continue
                data = r.json()
                if not isinstance(data, list):
                    continue
                source = str(params)
                for row in data:
                    first = (row.get("FirstName") or "").strip()
                    last = (row.get("LastName") or "").strip()
                    name = f"{first} {last}".strip()
                    if not name:
                        continue
                    try:
                        rating = float(row.get("FargoRating") or 0)
                    except (TypeError, ValueError):
                        continue
                    out.append({
                        "name": name,
                        "fargo_rating": rating,
                        "country": (row.get("Country") or "").strip() or None,
                        "source": source,
                    })
            except Exception as e:
                logger.warning("Fetch %s: %s", params, e)
    return out


def merged_by_name(rows: list[dict]) -> dict[str, float]:
    """Best (highest) fargo_rating per name."""
    by_name: dict[str, float] = {}
    for r in rows:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        rating = r.get("fargo_rating")
        if rating is None:
            continue
        try:
            f = float(rating)
        except (TypeError, ValueError):
            continue
        if name not in by_name or f > by_name[name]:
            by_name[name] = f
    return by_name


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def match_db_to_list(db_names: list[str], list_by_name: dict[str, float]) -> list[tuple[str, float, str]]:
    """For each db_name, find best list rating: exact match or one name is prefix of the other. Returns (db_name, rating, list_name_matched)."""
    list_names = sorted(list_by_name.keys(), key=len)
    result = []
    for db in db_names:
        dbn = _norm(db)
        if not dbn:
            continue
        best_rating = None
        best_list_name = None
        for list_name in list_names:
            ln = _norm(list_name)
            if dbn == ln:
                best_rating = list_by_name[list_name]
                best_list_name = list_name
                break
            if dbn.startswith(ln) or ln.startswith(dbn):
                r = list_by_name[list_name]
                if best_rating is None or r > best_rating:
                    best_rating = r
                    best_list_name = list_name
        if best_rating is not None and best_list_name is not None:
            result.append((db, best_rating, best_list_name))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Fargo Top-pool_opt_in from dashboard, save and import")
    parser.add_argument("--no-fetch", action="store_true", help="Use existing data/fargo_import_*.json if present")
    parser.add_argument("--no-import", action="store_true", help="Only fetch and save JSON; do not update DB")
    parser.add_argument("--dry-run", action="store_true", help="Do not write DB; show what would be imported")
    args = parser.parse_args()

    if args.no_fetch:
        try:
            candidates = list(DATA_DIR.glob("fargo_import_*.json"))
        except Exception:
            candidates = []
        if not candidates:
            logger.error("No existing fargo_import_*.json in data/")
            return 1
        path = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        logger.info("Using existing %s", path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw.get("players", raw) if isinstance(raw, dict) else raw
        if not isinstance(rows, list):
            rows = []
    else:
        rows = fetch_lists()
        if not rows:
            logger.error("No data from dashboard")
            return 1
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        out_path = DATA_DIR / f"fargo_import_{stamp}.json"
        payload = {"fetched_at": datetime.now(timezone.utc).isoformat(), "source": DASHBOARD_BASE, "players": rows}
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Saved %d players to %s", len(rows), out_path)

    list_by_name = merged_by_name(rows)
    logger.info("Merged %d unique names from list(s)", len(list_by_name))

    if args.no_import:
        return 0

    from database import get_database_manager
    from api.services import fargo_client

    conn = get_database_manager().get_connection()
    system_to_ranking = {"WPBA": "WPBA_Women", "WPA": "WPA_Women", "WPA_Men": "WPA_Men"}
    total_updated = 0
    try:
        for org, ranking_system in system_to_ranking.items():
            missing = fargo_client.get_names_missing_fargo(conn, org)
            if not missing:
                continue
            pairs = match_db_to_list(missing, list_by_name)
            if not pairs:
                continue
            if args.dry_run:
                logger.info("%s: would import %d Fargo ratings (of %d missing)", org, len(pairs), len(missing))
                total_updated += len(pairs)
                continue
            ratings_list = [
                {"player_name": name, "fargo_rating": rating, "fargo_source": "dashboard_import", "fargo_name_format": list_name}
                for name, rating, list_name in pairs
            ]
            updated, err = fargo_client.import_fargo_ratings_manual(conn, org, ratings_list)
            if err:
                logger.warning("%s: %s", org, err)
            else:
                total_updated += updated
                logger.info("%s: imported %d Fargo ratings", org, updated)
    finally:
        conn.close()

    logger.info("Total rows updated: %d", total_updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
