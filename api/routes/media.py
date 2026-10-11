"""
Media API: slideshow (weighted) and scrape trigger for WPBA/WPA pics and videos.
"""

import logging

from fastapi import APIRouter, Depends

from api.auth import require_admin
from api.services.live_topics import Topic
from api.services.live_updates import notify_data_changed
from api.services.media_store import get_slideshow_urls, count_media
from api.services.media_scraper import run_scrape

router = APIRouter(prefix="/api/media", tags=["media"])
logger = logging.getLogger(__name__)


@router.get("/slideshow")
async def slideshow(limit: int = 24):
    """
    Return a weighted sequence of media URLs for splash/background slideshow.
    Women (WPBA/WPA women) 2x men; Debbie Teichert at least 1 in every 8.
    """
    urls = get_slideshow_urls(limit=limit, women_weight=2.0, men_weight=1.0, debbie_every_n=8)
    return {"urls": urls}


@router.get("/count")
async def media_count():
    """Return number of items in media DB."""
    return {"count": count_media()}


@router.post("/scrape")
async def scrape_media(_admin: dict = Depends(require_admin)):
    """
    Scrape pics and videos from WPBA and WPA websites; save to media dir and DB.
    Run when you want to refresh the slideshow pool.
    Admin / super_admin only (Bearer JWT): it makes outbound requests and writes to disk and DB.
    """
    result = run_scrape()
    try:
        notify_data_changed(Topic.UPLOADS.value, message="Media scrape completed")
    except Exception as e:
        logger.warning("notify_data_changed failed (media scrape): %s", e)
    return result
