"""
YouTube Data API v3 search helper for Covert Ops.
Searches for a player's pool/billiards match videos. Requires YOUTUBE_API_KEY.
"""

import logging
import os
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def search_first_match_video(query: str, api_key: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Search YouTube for one video matching the query. Returns (video_url, video_title) or (None, None).
    Uses YOUTUBE_API_KEY env if api_key not provided.
    """
    key = api_key or os.getenv("YOUTUBE_API_KEY", "").strip()
    if not key:
        logger.debug("YOUTUBE_API_KEY not set; skipping YouTube search")
        return None, None
    try:
        with httpx.Client(timeout=15) as client:
            r = client.get(
                YOUTUBE_SEARCH_URL,
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": 1,
                    "key": key,
                },
            )
            if r.status_code != 200:
                logger.warning("YouTube API error %s: %s", r.status_code, r.text[:200])
                return None, None
            data = r.json()
            items = data.get("items") or []
            if not items:
                return None, None
            vid = items[0]
            vid_id = vid.get("id", {}).get("videoId")
            title = (vid.get("snippet") or {}).get("title") or ""
            if not vid_id:
                return None, None
            url = f"https://www.youtube.com/watch?v={vid_id}"
            return url, title
    except Exception as e:
        logger.warning("YouTube search failed: %s", e)
        return None, None
