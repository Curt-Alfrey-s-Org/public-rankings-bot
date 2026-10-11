"""
Admin messages service.
Stores Fargo failures, scrape failures, and other admin-reviewable messages.
Easier to read than logs; displayed in Settings > System & messages.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from database import get_engine
engine = get_engine()

logger = logging.getLogger(__name__)

# Categories for admin messages (human-readable in UI)
CATEGORY_FARGO_FAILED = "fargo_failed"
CATEGORY_SCRAPE_FAILED = "scrape_failed"
CATEGORY_WARNING = "warning"
CATEGORY_INFO = "info"


def add_message(category: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """
    Add an admin message for review. Stored in admin_messages table.
    """
    try:
        details_json = json.dumps(details) if details else None
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO admin_messages (category, message, details) VALUES (:cat, :msg, :det)"
                ),
                {"cat": category, "msg": message, "det": details_json},
            )
            conn.commit()
    except Exception as e:
        logger.warning("Failed to add admin message: %s", e)


def add_fargo_failed(org_code: str, failed_players: List[str], error_summary: Optional[str] = None) -> None:
    """Add Fargo sync failure message with player names."""
    if not failed_players:
        return
    msg = f"Fargo sync ({org_code}): {len(failed_players)} player(s) could not be updated."
    if error_summary:
        msg += f" {error_summary}"
    add_message(
        CATEGORY_FARGO_FAILED,
        msg,
        {"org_code": org_code, "failed_players": failed_players[:100], "count": len(failed_players)},
    )


def add_scrape_failed(source: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Add scrape failure message."""
    add_message(CATEGORY_SCRAPE_FAILED, message, {"source": source, **(details or {})})


def add_fargo_problem_names(org_code: str, problem_players: List[str], reason: str = "Could not fetch Fargo rating") -> None:
    """
    Track players that couldn't be matched to Fargo ratings.
    Allows admin to manually map source names (e.g., "Alex Kazakis" → "Kazakis, Alexander").
    
    Args:
        org_code: Organization code (WPBA, WPA_Men, etc.)
        problem_players: List of player names that need manual attention
        reason: Why the lookup failed (e.g., "Not found in FairMatch", "Name mismatch")
    """
    if not problem_players:
        return
    
    msg = f"Fargo problem names ({org_code}): {len(problem_players)} player(s) need manual mapping. {reason}"
    details = {
        "org_code": org_code,
        "reason": reason,
        "players_with_issues": problem_players[:50],  # First 50 for UI display
        "count": len(problem_players),
        "note": "Admin can manually update fargo_source_name in rankings table to specify which FargoRate name to use"
    }
    add_message(
        "fargo_problem_names",
        msg,
        details
    )


def get_messages(
    category: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Get admin messages for display. Returns list of {timestamp, message, category, details}.
    """
    try:
        with engine.connect() as conn:
            sql = "SELECT category, message, details, created_at FROM admin_messages"
            params: Dict[str, Any] = {"lim": limit}
            if category:
                sql += " WHERE category = :cat"
                params["cat"] = category
            sql += " ORDER BY created_at DESC LIMIT :lim"
            params["lim"] = limit
            result = conn.execute(text(sql), params)
            rows = result.fetchall()
            out = []
            for row in rows:
                cat, msg, det, ts = row
                details = json.loads(det) if det else None
                out.append({
                    "category": cat,
                    "message": msg,
                    "details": details,
                    "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                })
            return out
    except Exception as e:
        logger.warning("Failed to get admin messages: %s", e)
        return []
