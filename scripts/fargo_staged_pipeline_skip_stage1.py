"""
Staged Fargo sync pipeline:
1) Dashboard Top-pool_opt_in (fast)
2) Smart name matcher (medium)
3) Sequential FairMatch mop-up (slow)

Outputs per-stage percentages and a final list of names still missing.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, "/home/ansible/rankings-bot/Rankings-Bot")

from api.services import fargo_client
from api.services.fairmatch_scraper import lookup_rating
from database import get_database_manager
from scripts.find_fargo_matches import generate_name_variations


def _normalize_name(name: str) -> str:
    return " ".join((name or "").split()).strip()


def _get_missing_names(conn, org_code: str) -> List[str]:
    return fargo_client.get_names_missing_fargo(conn, org_code)


def _get_distinct_names(conn, org_code: str) -> List[str]:
    return fargo_client.get_distinct_player_names(conn, org_code)


def _update_rows(conn, rows: List[Dict[str, any]]) -> int:
    if not rows:
        return 0
    return fargo_client.update_rankings_with_fargo(conn, rows)


def _map_dashboard_to_db_names(conn, org_code: str, dashboard_rows: List[Dict[str, any]]) -> List[Dict[str, any]]:
    db_names = _get_distinct_names(conn, org_code)
    normalized_to_db: Dict[str, List[str]] = {}
    for name in db_names:
        key = _normalize_name(name)
        if key:
            normalized_to_db.setdefault(key, []).append(name)

    out: List[Dict[str, any]] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for row in dashboard_rows:
        name = (row.get("player_name") or row.get("player_id") or row.get("name") or "").strip()
        rating = row.get("fargo_rating") or row.get("rating")
        updated_at = row.get("updated_at", now_iso)
        if not name or rating is None:
            continue
        norm = _normalize_name(name)
        db_matches = normalized_to_db.get(norm, [])
        for db_name in db_matches:
            out.append({
                "player_name": db_name,
                "fargo_rating": float(rating),
                "updated_at": updated_at,
            })
    return out


def _percent(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * part / total, 1)


def stage1_dashboard(conn, org_code: str) -> int:
    dashboard_rows = fargo_client.fetch_fargo_ratings_from_dashboard()
    mapped = _map_dashboard_to_db_names(conn, org_code, dashboard_rows)
    return _update_rows(conn, mapped)


def stage2_smart_match(
    conn,
    org_code: str,
    delay: float,
    max_consecutive_not_found: int,
    review_path: str,
) -> Tuple[int, List[str]]:
    missing = _get_missing_names(conn, org_code)
    if not missing:
        return 0, []

    updated_rows: List[Dict[str, any]] = []
    ambiguous: List[Dict[str, any]] = []
    consecutive_not_found = 0

    for idx, player_name in enumerate(missing, 1):
        variations = generate_name_variations(player_name)
        matches: List[Tuple[str, float]] = []

        for variation in variations:
            rating, error = lookup_rating(variation)
            if rating is not None:
                matches.append((variation, rating))
            time.sleep(delay)

        if not matches:
            consecutive_not_found += 1
            if consecutive_not_found >= max_consecutive_not_found:
                break
            continue

        consecutive_not_found = 0
        unique_ratings = {r for _, r in matches}
        if len(unique_ratings) == 1:
            chosen_variation, chosen_rating = matches[0]
            updated_rows.append({
                "player_name": player_name,
                "fargo_rating": float(chosen_rating),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "matched_name": chosen_variation,
            })
        else:
            ambiguous.append({
                "player_name": player_name,
                "matches": [{"name": v, "rating": r} for v, r in matches],
            })

    if ambiguous:
        with open(review_path, "w", encoding="utf-8") as f:
            json.dump(ambiguous, f, indent=2)

    updated = _update_rows(conn, updated_rows)
    return updated, [row["player_name"] for row in updated_rows]


def stage3_sequential_mop_up(
    conn,
    org_code: str,
    delay: float,
    max_consecutive_not_found: int,
    max_retries: int,
) -> int:
    missing = _get_missing_names(conn, org_code)
    if not missing:
        return 0

    updated_rows: List[Dict[str, any]] = []
    consecutive_not_found = 0

    for player_name in missing:
        last_error: Optional[str] = None
        rating: Optional[float] = None

        for attempt in range(max_retries + 1):
            rating, last_error = lookup_rating(player_name)
            if rating is not None:
                break
            if last_error and any(x in last_error.lower() for x in ["timeout", "connection", "reset", "refused"]):
                time.sleep(1.5 * (attempt + 1))
                continue
            break

        if rating is not None:
            updated_rows.append({
                "player_name": player_name,
                "fargo_rating": float(rating),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            consecutive_not_found = 0
        else:
            consecutive_not_found += 1
            if consecutive_not_found >= max_consecutive_not_found:
                break

        time.sleep(delay)

    return _update_rows(conn, updated_rows)


def run_pipeline_for_org(
    org_code: str,
    delay_medium: float,
    delay_slow: float,
    max_consecutive_not_found: int,
    max_retries: int,
    output_dir: str,
) -> None:
    db = get_database_manager()
    conn = db.get_connection()

    try:
        initial_missing = len(_get_missing_names(conn, org_code))
        print(f"\n[{org_code}] Initial missing: {initial_missing}")

        # Stage 1 - SKIPPED (top 100 already handled)
        stage1_updated = 0
        missing_after_stage1 = initial_missing
        stage1_delta = 0
        print(
            f"[{org_code}] Stage 1 (dashboard): SKIPPED - top 100 already handled"
        )

        # Stage 2
        review_path = f"{output_dir}/{org_code}_ambiguous.json"
        stage2_updated, _ = stage2_smart_match(
            conn,
            org_code,
            delay_medium,
            max_consecutive_not_found,
            review_path,
        )
        missing_after_stage2 = len(_get_missing_names(conn, org_code))
        stage2_delta = missing_after_stage1 - missing_after_stage2
        print(
            f"[{org_code}] Stage 2 (smart match): updated {stage2_updated}, "
            f"reduced missing by {stage2_delta} ({_percent(stage2_delta, initial_missing)}%)"
        )

        # Stage 3
        stage3_updated = stage3_sequential_mop_up(
            conn,
            org_code,
            delay_slow,
            max_consecutive_not_found,
            max_retries,
        )
        missing_after_stage3 = len(_get_missing_names(conn, org_code))
        stage3_delta = missing_after_stage2 - missing_after_stage3
        print(
            f"[{org_code}] Stage 3 (mop-up): updated {stage3_updated}, "
            f"reduced missing by {stage3_delta} ({_percent(stage3_delta, initial_missing)}%)"
        )

        # Final report
        final_missing = _get_missing_names(conn, org_code)
        not_found_path = f"{output_dir}/{org_code}_not_found.txt"
        with open(not_found_path, "w", encoding="utf-8") as f:
            for name in final_missing:
                f.write(f"{name}\n")

        print(
            f"[{org_code}] Final missing: {len(final_missing)} "
            f"({_percent(len(final_missing), initial_missing)}% of original)"
        )
        print(f"[{org_code}] Not found list: {not_found_path}")
        print(f"[{org_code}] Ambiguous matches: {review_path}")

    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Staged Fargo sync pipeline")
    parser.add_argument(
        "--system",
        action="append",
        choices=["WPBA_Women", "WPA_Women", "WPA_Men"],
        help="Run for a specific system (can repeat). Defaults to all.",
    )
    parser.add_argument("--delay-medium", type=float, default=0.8, help="Delay between smart-match lookups")
    parser.add_argument("--delay-slow", type=float, default=1.2, help="Delay between mop-up lookups")
    parser.add_argument("--max-consecutive-not-found", type=int, default=5, help="Stop after N consecutive not found")
    parser.add_argument("--max-retries", type=int, default=2, help="Retries for transient errors in mop-up")
    parser.add_argument("--output-dir", type=str, default=".", help="Output directory for reports")

    args = parser.parse_args()
    systems = args.system or ["WPA_Women", "WPA_Men", "WPBA_Women"]

    for system in systems:
        run_pipeline_for_org(
            system,
            0.5,  # faster delay_medium
            0.8,  # faster delay_slow
            args.max_consecutive_not_found,
            args.max_retries,
            args.output_dir,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
