"""
Messages Routes
Provides stored messages and alerts (admin_messages table for Fargo/scrape failures, etc.).
"""

from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, Depends, Query

from api.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()


def _from_admin_messages(category: Optional[str], limit: int) -> list:
    """Read from admin_messages table; returns list of {timestamp, message, category, details}."""
    try:
        from api.services.admin_messages import get_messages
        rows = get_messages(category=category, limit=limit)
        return [{"timestamp": r["timestamp"], "message": r["message"], "category": r["category"], "details": r.get("details")} for r in rows]
    except Exception as exc:
        logger.debug("admin_messages get_messages: %s", exc)
        return []


@router.get("")
async def list_messages(
    category: Optional[str] = Query(None, description="Filter by admin_messages.category"),
    limit: int = Query(100, ge=1, le=500),
    _user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """
    List admin messages (Fargo/scrape failures, warnings, etc.). Admin or super_admin only.
    """
    rows = _from_admin_messages(category, limit)
    messages: List[Dict[str, Any]] = [
        {
            "timestamp": r["timestamp"],
            "message": r["message"],
            "category": r["category"],
            "details": r.get("details"),
        }
        for r in rows
    ]
    return {"messages": messages, "total": len(messages)}

