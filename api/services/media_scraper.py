"""
Scrape pics and videos from WPBA and WPA websites; save to media dir and media DB.
Women 2x men weighting and Debbie Teichert as contributor are applied in media_store.get_slideshow_urls.
"""

import logging
import re
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from api.services.media_store import add_media

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEDIA_DIR = PROJECT_ROOT / "media"
MEDIA_IMAGE = MEDIA_DIR / "image"
MEDIA_VIDEO = MEDIA_DIR / "video"


def _path_to_serve_path(relative_path: Path) -> str:
    return f"/api/assets/serve/{relative_path.as_posix()}"

logger = logging.getLogger(__name__)

# Seed URLs for scraping (news/gallery pages that contain img tags)
WPBA_PAGES = [
    "https://wpba.com/",
    "https://wpba.com/events-official",
    "https://wpba.com/players",
]
WPA_PAGES = [
    "https://wpapool.com/",
    "https://wpapool.com/news/",
]

CONTRIBUTOR_DEBBIE = "debbie_teichert"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXT = {".mp4", ".webm", ".mov"}


def _is_media_url(href: str) -> bool:
    if not href or href.startswith("data:"):
        return False
    path = urlparse(href).path.lower()
    return any(path.endswith(e) for e in list(IMAGE_EXT) + list(VIDEO_EXT))


def _category_from_source(source: str, page_url: str) -> str:
    if "wpba" in source.lower():
        return "women"
    if "wpa" in source.lower():
        if "women" in page_url.lower() or "female" in page_url.lower():
            return "women"
        if "men" in page_url.lower():
            return "men"
        return "women"
    return "women"


def _is_debbie_teichert(url: str, page_html: str) -> bool:
    combined = (url + " " + (page_html or ""))[:5000].lower()
    return "debbie" in combined and "teichert" in combined


def _download_and_save(client: httpx.Client, url: str) -> Path | None:
    try:
        r = client.get(url, follow_redirects=True, timeout=15)
        r.raise_for_status()
        path = urlparse(url).path
        ext = Path(path).suffix.lower()
        if ext not in IMAGE_EXT and ext not in VIDEO_EXT:
            ext = ".jpg"
        name = f"{uuid.uuid4().hex}{ext}"
        subdir = MEDIA_VIDEO if ext in VIDEO_EXT else MEDIA_IMAGE
        subdir.mkdir(parents=True, exist_ok=True)
        dest = subdir / name
        dest.write_bytes(r.content)
        return dest.relative_to(MEDIA_DIR)
    except Exception as e:
        logger.debug("Download failed %s: %s", url, e)
        return None


def scrape_source(source: str, pages: list[str]) -> int:
    """Scrape pages for a source (wpba/wpa), download media, add to store. Returns count added."""
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_IMAGE.mkdir(exist_ok=True)
    MEDIA_VIDEO.mkdir(exist_ok=True)
    added = 0
    with httpx.Client(headers={"User-Agent": "RankingsBot/1.0"}) as client:
        for page_url in pages:
            try:
                r = client.get(page_url, follow_redirects=True, timeout=15)
                r.raise_for_status()
                html = r.text
            except Exception as e:
                logger.warning("Fetch %s failed: %s", page_url, e)
                continue
            # Extract img src and video source
            img_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I)
            video_urls = re.findall(r'<video[^>]+src=["\']([^"\']+)["\']', html, re.I)
            video_urls += re.findall(r'<source[^>]+src=["\']([^"\']+)["\']', html, re.I)
            all_urls = []
            for u in img_urls + video_urls:
                full = urljoin(page_url, u.strip())
                if _is_media_url(full):
                    all_urls.append(full)
            category = _category_from_source(source, page_url)
            for media_url in all_urls[:30]:
                rel = _download_and_save(client, media_url)
                if rel is None:
                    continue
                path = _path_to_serve_path(rel)
                contributor = CONTRIBUTOR_DEBBIE if _is_debbie_teichert(media_url, html) else None
                if add_media(path, source, category, contributor):
                    added += 1
    return added


def run_scrape() -> dict:
    """Run WPBA and WPA scrapes; return counts."""
    wpba_count = scrape_source("wpba", WPBA_PAGES)
    wpa_count = scrape_source("wpa", WPA_PAGES)
    return {"wpba": wpba_count, "wpa": wpa_count, "total": wpba_count + wpa_count}
