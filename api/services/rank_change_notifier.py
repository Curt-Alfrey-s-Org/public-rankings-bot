"""
Rank change detection and email notification service.
Compares current rankings with history, sends alerts via email_service.send_ranking_alert.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Map org_code to ranking_system values in DB
ORG_TO_SYSTEM = {
    "WPBA": "WPBA_Women",
    "WPBA_Women": "WPBA_Women",
    "WPA": "WPA_Women",
    "WPA_Women": "WPA_Women",
    "WPA_Men": "WPA_Men",
}


def detect_rank_changes(db_manager, org_code: str) -> List[Dict[str, Any]]:
    """
    Compare current rankings with ranking_changes history.
    Returns list of changes: {player_name, old_rank, new_rank, movement, points_change, ...}
    """
    changes = []
    try:
        system = ORG_TO_SYSTEM.get(org_code, org_code)
        movement = db_manager.get_movement(system, limit=200)
        for m in movement:
            changes.append({
                "player_name": m.get("player_name", ""),
                "old_rank": m.get("old_rank"),
                "new_rank": m.get("new_rank"),
                "old_points": m.get("old_points"),
                "new_points": m.get("new_points"),
                "change_type": m.get("change_type", "change"),
                "change_date": m.get("change_date"),
                "ranking_system": system,
                "movement": _format_movement(m.get("old_rank"), m.get("new_rank")),
                "points_change": m.get("new_points") - m.get("old_points") if m.get("old_points") and m.get("new_points") else None,
            })
        logger.info(f"Detected {len(changes)} rank changes for {org_code}")
    except Exception as e:
        logger.exception(f"Failed to detect rank changes for {org_code}: {e}")
    return changes


def _format_movement(old_rank: Optional[int], new_rank: Optional[int]) -> str:
    """Format rank movement as +2, -1, etc."""
    if old_rank is None or new_rank is None:
        return ""
    diff = old_rank - new_rank
    if diff > 0:
        return f"+{diff}"
    if diff < 0:
        return str(diff)
    return "0"


def send_rank_change_alerts(
    db_manager,
    changes: List[Dict[str, Any]],
    dry_run: bool = False,
    already_sent: Optional[set] = None,
) -> int:
    """
    Email users when rank changes. Uses email_rank_subscriptions and email_service.send_ranking_alert.
    Returns count of alerts sent.
    """
    # Postgres-first architecture: accept any manager exposing subscription methods.
    if not hasattr(db_manager, "get_subscriptions_for_player_system"):
        logger.warning("db_manager missing get_subscriptions_for_player_system; skipping rank change alerts")
        return 0

    sent = 0
    already_sent = already_sent or set()

    for change in changes:
        player_name = change.get("player_name", "")
        system = change.get("ranking_system", "")

        try:
            subs = db_manager.get_subscriptions_for_player_system(player_name, system)
            if not subs:
                continue

            ranking_change = {
                "player_name": player_name,
                "old_rank": change.get("old_rank"),
                "new_rank": change.get("new_rank"),
                "movement": change.get("movement", ""),
                "points_change": change.get("points_change"),
                "division": "",
                "association": system,
            }

            from api.services.email_service import send_ranking_alert

            for sub in subs:
                email = sub.get("email", "")
                key = (email, player_name, system)
                if key in already_sent:
                    continue
                if dry_run:
                    logger.info(f"[DRY-RUN] Would send rank alert to {email} for {player_name}")
                    sent += 1
                    already_sent.add(key)
                elif send_ranking_alert(email, ranking_change):
                    sent += 1
                    already_sent.add(key)
        except Exception as e:
            logger.exception(f"Failed to send alert for {player_name}: {e}")

    return sent
