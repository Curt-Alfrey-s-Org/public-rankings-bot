"""
Staged Fargo sync pipeline:
1) Dashboard Top-pool_opt_in (fast)
2) Smart name matcher on remaining NULL ratings (medium)
3) Sequential FairMatch mop-up on remaining (slow)

Provides per-stage metrics and logs final report to admin_messages.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from api.services import admin_messages
from api.services.fairmatch_scraper import lookup_rating
from api.services.fargo_name_variations import generate_name_variations
from api.services import fargo_client


def _normalize_name(name: str) -> str:
    return " ".join((name or "").split()).strip()


def _get_missing_names(conn, org_code: str) -> List[str]:
    return fargo_client.get_names_missing_fargo(conn, org_code)


def _get_distinct_names(conn, org_code: str) -> List[str]:
    return fargo_client.get_distinct_player_names(conn, org_code)


def _update_rows(conn, rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    return fargo_client.update_rankings_with_fargo(conn, rows)


def _percent(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * part / total, 1)


def _map_dashboard_to_db_names(conn, org_code: str, dashboard_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    db_names = _get_distinct_names(conn, org_code)
    normalized_to_db: Dict[str, List[str]] = {}
    for name in db_names:
        key = _normalize_name(name)
        if key:
            normalized_to_db.setdefault(key, []).append(name)

    out: List[Dict[str, Any]] = []
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


def _stage_metrics(stage_name: str, total_checked: int, found: int, not_found: int, ambiguous: int = 0) -> Dict[str, Any]:
    return {
        "stage": stage_name,
        "total_checked": total_checked,
        "found": found,
        "not_found": not_found,
        "ambiguous": ambiguous,
        "success_pct": _percent(found, total_checked),
    }


def _stage1_dashboard(conn, org_code: str, initial_missing: int) -> Dict[str, Any]:
    dashboard_rows = fargo_client.fetch_fargo_ratings_from_dashboard()
    mapped = _map_dashboard_to_db_names(conn, org_code, dashboard_rows)
    _update_rows(conn, mapped)

    missing_after = len(_get_missing_names(conn, org_code))
    found = max(0, initial_missing - missing_after)
    not_found = max(0, initial_missing - found)
    return _stage_metrics("dashboard", initial_missing, found, not_found)


def _stage2_smart_match(
    conn,
    org_code: str,
    delay: float,
    max_consecutive_not_found: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    missing = _get_missing_names(conn, org_code)
    if not missing:
        return _stage_metrics("smart_match", 0, 0, 0), []

    updated_rows: List[Dict[str, Any]] = []
    ambiguous: List[Dict[str, Any]] = []
    consecutive_not_found = 0
    checked = 0

    for player_name in missing:
        checked += 1
        variations = generate_name_variations(player_name)
        matches: List[Tuple[str, float]] = []

        for variation in variations:
            rating, _error = lookup_rating(variation)
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

    updated = _update_rows(conn, updated_rows)
    not_found = max(0, checked - updated - len(ambiguous))
    metrics = _stage_metrics("smart_match", checked, updated, not_found, ambiguous=len(ambiguous))
    return metrics, ambiguous


def _stage3_mop_up(
    conn,
    org_code: str,
    delay: float,
    max_consecutive_not_found: int,
    max_retries: int,
) -> Dict[str, Any]:
    missing = _get_missing_names(conn, org_code)
    if not missing:
        return _stage_metrics("mop_up", 0, 0, 0)

    updated_rows: List[Dict[str, Any]] = []
    consecutive_not_found = 0
    checked = 0

    for player_name in missing:
        checked += 1
        rating: Optional[float] = None
        last_error: Optional[str] = None

        for attempt in range(max_retries + 1):
            rating, last_error = lookup_rating(player_name)
            if rating is not None:
                break
            if last_error and any(x in last_error.lower() for x in ("timeout", "connection", "reset", "refused")):
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

    updated = _update_rows(conn, updated_rows)
    not_found = max(0, checked - updated)
    return _stage_metrics("mop_up", checked, updated, not_found)


def run_staged_sync(
    conn,
    org_code: str,
    *,
    delay_medium: float = 0.8,
    delay_slow: float = 1.2,
    max_consecutive_not_found: int = 5,
    max_retries: int = 2,
    log_to_admin: bool = True,
) -> Dict[str, Any]:
    """
    Run staged Fargo sync and return a report dict.
    Logs a final report + remaining names to admin_messages when log_to_admin is True.
    """
    initial_missing = len(_get_missing_names(conn, org_code))

    stage1 = _stage1_dashboard(conn, org_code, initial_missing)
    stage2, ambiguous = _stage2_smart_match(
        conn,
        org_code,
        delay=delay_medium,
        max_consecutive_not_found=max_consecutive_not_found,
    )
    stage3 = _stage3_mop_up(
        conn,
        org_code,
        delay=delay_slow,
        max_consecutive_not_found=max_consecutive_not_found,
        max_retries=max_retries,
    )

    remaining_names = _get_missing_names(conn, org_code)
    final_missing = len(remaining_names)

    report = {
        "org_code": org_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "initial_missing": initial_missing,
        "final_missing": final_missing,
        "stages": {
            "stage1": stage1,
            "stage2": stage2,
            "stage3": stage3,
        },
        "ambiguous_matches": ambiguous,
        "remaining_names_count": final_missing,
        "remaining_names": remaining_names,
    }

    if log_to_admin:
        details = {
            "org_code": org_code,
            "initial_missing": initial_missing,
            "final_missing": final_missing,
            "stages": report["stages"],
            "ambiguous_count": len(ambiguous),
            "remaining_names_count": final_missing,
            "remaining_names": remaining_names[:200],
        }
        admin_messages.add_message(
            admin_messages.CATEGORY_INFO,
            f"Fargo staged sync complete for {org_code}: {initial_missing} -> {final_missing} missing",
            details,
        )

    return report
