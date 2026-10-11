"""
Future tournament events from WPA and WPBA (scraped).
Uses cached scrape (30 min TTL); optional skip_cache for refresh.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Query

from api.services.events_scraper import get_future_events

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/future")
def future_events(
    limit: int = Query(default=50, ge=1, le=100),
    location: str | None = Query(default=None, description="Filter by location (e.g. Ft Lauderdale)"),
    days: int | None = Query(default=None, ge=1, le=365, description="Only events within next N days"),
    skip_cache: bool = Query(default=False, description="Bypass cache and scrape fresh (e.g. admin refresh)"),
):
    """Return future tournament events from WPBA and WPA websites (cached 30 min)."""
    events = get_future_events(skip_cache=skip_cache)
    if location and location.strip():
        loc_lower = location.strip().lower()
        events = [e for e in events if e.get("location") and loc_lower in (e.get("location") or "").lower()]
    if days is not None:
        cutoff = (datetime.now().date() + timedelta(days=days)).isoformat()
        events = [e for e in events if (e.get("start_date") or "") <= cutoff]
    return {"events": events[:limit]}
