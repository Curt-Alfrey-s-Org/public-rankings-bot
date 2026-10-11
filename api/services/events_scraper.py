"""
Fetch future tournament events from WPBA and WPA websites.
Returns structured list for home and Future Tourneys page.

Production-ready: TTL cache, retries with backoff, return stale on failure
(per industry practice for external scrape/API dependencies).
"""

import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

WPBA_EVENTS_URL = "https://wpba.com/events-official"
WPA_CALENDAR_URL = "https://wpapool.com/calendar-2/"

USER_AGENT = "RankingsBot/1.0 (events)"
DEFAULT_TIMEOUT = 20
CACHE_TTL_SECONDS = 30 * 60  # 30 minutes
MAX_RETRIES = 3
RETRY_BACKOFF = (2, 4, 8)  # seconds

# In-memory cache: (events_list, expires_at); guarded by _cache_lock
_events_cache: Optional[tuple[list[dict], datetime]] = None
_cache_lock = threading.Lock()


def _set_cached(events: list[dict], ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
    """Store events in cache with TTL."""
    expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    with _cache_lock:
        global _events_cache
        _events_cache = (events, expires)


def clear_future_events_cache() -> None:
    """Clear in-memory cache (e.g. for admin refresh or tests)."""
    with _cache_lock:
        global _events_cache
        _events_cache = None
    logger.info("Future events cache cleared")


def _fetch_with_retry(
    client: httpx.Client,
    url: str,
) -> Optional[str]:
    """
    GET url with retries on 5xx, 429, and timeout.
    Returns response text or None on failure.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            r = client.get(url)
            if r.status_code in (429, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                logger.warning(
                    "Events scraper got %s from %s; retry %s/%s in %ss",
                    r.status_code,
                    url[:50],
                    attempt + 1,
                    MAX_RETRIES,
                    wait,
                )
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.text
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError) as e:
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                logger.warning(
                    "Events scraper error %s for %s; retry %s/%s in %ss",
                    type(e).__name__,
                    url[:50],
                    attempt + 1,
                    MAX_RETRIES,
                    wait,
                )
                time.sleep(wait)
            else:
                logger.warning("Events scraper failed for %s after %s retries: %s", url[:50], MAX_RETRIES, e)
    return None


def _parse_wpba_events(html: str, base_url: str) -> list[dict]:
    """Parse WPBA events-official page for event name, date range, location, url."""
    events = []
    date_range_pattern = re.compile(
        r'([A-Za-z]+\s+\d{1,2},\s+\d{4})\s*[–\-&ndash;]\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})',
        re.IGNORECASE,
    )
    link_pattern = re.compile(
        r'<a\s+[^>]*href=["\'](https://wpba\.com/[^"\']*events[^"\']*)["\'][^>]*>([^<]+)</a>',
        re.IGNORECASE,
    )
    md_link = re.compile(r'\[([^\]]+)\]\((https://wpba\.com/[^)]+)\)')
    seen_urls: set[str] = set()
    for m in date_range_pattern.finditer(html):
        start_s, end_s = m.group(1), m.group(2)
        try:
            start_d = datetime.strptime(start_s.strip(), "%b %d, %Y")
            end_d = datetime.strptime(end_s.strip(), "%b %d, %Y")
            if end_d.date() < datetime.now().date():
                continue
        except ValueError:
            continue
        start_pos = max(0, m.start() - 1200)
        block = html[start_pos : m.end() + 300]
        name, url = None, None
        for link_m in list(link_pattern.finditer(block))[-1:]:
            url, name = link_m.group(1), link_m.group(2).strip()
            if "event" in url.lower() and url not in seen_urls:
                break
        if (not name or not url) and md_link.finditer(block):
            for link_m in list(md_link.finditer(block))[-1:]:
                name, url = link_m.group(1).strip(), link_m.group(2)
                if "event" in url.lower() and url not in seen_urls:
                    break
        if not name or not url or url in seen_urls:
            continue
        seen_urls.add(url)
        loc_match = re.search(r'\d+[\w\s,.#]+(?:AL|FL|NY|MI|NH|TN|WI)\s*\d{5}', block)
        if loc_match:
            location = loc_match.group(0).strip()[:200]
        else:
            city_match = re.search(
                r'((?:Ft\.?|Fort)\s+Lauderdale|Las\s+Vegas|Orlando|Chicago|New\s+York)[^<]*(?:,\s*)?(?:FL|NV|IL|NY)?',
                block,
                re.IGNORECASE,
            )
            location = city_match.group(0).strip()[:200] if city_match else None
        events.append({
            "name": name[:300] if name else "Event",
            "start_date": start_d.strftime("%Y-%m-%d"),
            "end_date": end_d.strftime("%Y-%m-%d"),
            "location": location,
            "url": url,
            "source": "WPBA",
        })
    return events


def _parse_wpa_calendar(html: str, base_url: str) -> list[dict]:
    """Parse WPA calendar-2 page for event titles and dates (future only)."""
    events = []
    date_pattern = re.compile(
        r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}',
    )
    link_pattern = re.compile(r'<a\s+[^>]*href=["\'](https://wpapool\.com/[^"\']+)["\'][^>]*>([^<]+)</a>')
    today = datetime.now().date()
    for h2_match in re.finditer(r'<h2[^>]*>([^<]+)</h2>', html, re.IGNORECASE):
        title = re.sub(r'<[^>]+>', '', h2_match.group(1)).strip()
        if not title or title.startswith('Calendar') or 'Past and upcoming' in title:
            continue
        block = html[h2_match.end() : h2_match.end() + 600]
        date_m = date_pattern.search(block)
        if not date_m:
            continue
        try:
            dt = datetime.strptime(date_m.group(0), "%B %d, %Y")
            if dt.date() < today:
                continue
        except ValueError:
            continue
        url = base_url
        link_m = link_pattern.search(block)
        if link_m:
            url = link_m.group(1)
            if not title or title in ('Events', 'News'):
                title = link_m.group(2).strip() or title
        source = "WPA Women" if "women" in title.lower() or "woman" in title.lower() else "WPA Men"
        events.append({
            "name": title[:300],
            "start_date": dt.strftime("%Y-%m-%d"),
            "end_date": dt.strftime("%Y-%m-%d"),
            "location": None,
            "url": url,
            "source": source,
        })
    lines = html.split('\n')
    for i, line in enumerate(lines):
        if not line.strip().startswith('## '):
            continue
        title = re.sub(r'<[^>]+>', '', line.replace('##', '')).strip()
        if not title or title.startswith('Calendar') or 'Past and upcoming' in title:
            continue
        date_str = None
        url = base_url
        for j in range(i + 1, min(i + 5, len(lines))):
            date_m = date_pattern.search(lines[j])
            link_m = link_pattern.search(lines[j])
            if link_m:
                url = link_m.group(1)
            if date_m:
                date_str = date_m.group(0)
                break
        if not date_str:
            continue
        try:
            dt = datetime.strptime(date_str, "%B %d, %Y")
            if dt.date() < today:
                continue
        except ValueError:
            continue
        source = "WPA Women" if "women" in title.lower() or "woman" in title.lower() else "WPA Men"
        events.append({
            "name": title[:300],
            "start_date": dt.strftime("%Y-%m-%d"),
            "end_date": dt.strftime("%Y-%m-%d"),
            "location": None,
            "url": url,
            "source": source,
        })
    return events


def _fetch_fresh() -> list[dict]:
    """Fetch WPBA and WPA pages and return combined list (no cache)."""
    result: list[dict] = []
    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=DEFAULT_TIMEOUT,
    ) as client:
        html = _fetch_with_retry(client, WPBA_EVENTS_URL)
        if html:
            result.extend(_parse_wpba_events(html, WPBA_EVENTS_URL))
        else:
            logger.warning("WPBA events fetch failed after retries")
        html = _fetch_with_retry(client, WPA_CALENDAR_URL)
        if html:
            result.extend(_parse_wpa_calendar(html, WPA_CALENDAR_URL))
        else:
            logger.warning("WPA calendar fetch failed after retries")
    result.sort(key=lambda x: (x["start_date"], x["name"]))
    return result


def get_future_events(*, skip_cache: bool = False) -> list[dict]:
    """
    Return future tournament events from WPBA and WPA websites.

    Uses in-memory cache (TTL 30 min) to avoid hammering external sites.
    On scrape failure, returns last known good data if available (graceful degradation).
    """
    now = datetime.now(timezone.utc)
    with _cache_lock:
        if _events_cache is not None:
            data, expires = _events_cache
            if not skip_cache and now < expires:
                return list(data)
            stale = data
        else:
            stale = None

    if skip_cache:
        stale = None

    try:
        fresh = _fetch_fresh()
        _set_cached(fresh)
        return fresh
    except Exception as e:
        logger.warning("Future events scrape failed: %s", e)
        if stale is not None:
            logger.info("Returning stale cache (%s events)", len(stale))
            return list(stale)
        return []
