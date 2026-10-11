"""
Splash videos for mobile app: rotate between repo video and DB (media) video.
GET /api/v1/splash-videos returns [url1, url2] for 10s fade-in/out splash.
"""
import os
import logging
from fastapi import APIRouter, Request

router = APIRouter(tags=["splash-v1"])
logger = logging.getLogger(__name__)
REPO_SPLASH_PATH = "/assets/video/grok-video-a1fee053-2343-4013-a0de-0445458248cf.mp4"

def _base_url(request: Request) -> str:
    base = os.getenv("PUBLIC_API_URL", "").strip()
    if base:
        return base.rstrip("/")
    return str(request.base_url).rstrip("/")

@router.get("/splash-videos")
async def get_splash_videos(request: Request):
    base = _base_url(request)
    video1 = base + REPO_SPLASH_PATH
    video2 = video1
    try:
        from api.services.media_store import get_slideshow_urls
        paths = get_slideshow_urls(limit=20, women_weight=2.0, men_weight=1.0, debbie_every_n=8)
        for p in (paths or []):
            if p and ".mp4" in (p or "").lower():
                video2 = (base + p) if (p or "").startswith("/") else (base + "/" + p)
                break
    except Exception as e:
        logger.warning("Could not load slideshow video URL: %s", e)
    return {"videos": [video1, video2]}
