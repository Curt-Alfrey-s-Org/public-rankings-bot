"""
Discover past (and upcoming) tournament events from WPBA and WPA for history scraping.
Returns event name, date, location, event URL, and bracket URL when available (e.g. ExternalPool).

Uses same sites as api.services.events_scraper (WPBA events-official, WPA calendar-2).
Future events on the Home tab are served from events_scraper (cached). This module
feeds the tournament history / enhanced scraper pipeline.
"""

import logging
import re
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin

from scrapers.fetch_utils import get_with_retry

logger = logging.getLogger(__name__)

WPBA_EVENTS_OFFICIAL = "https://wpba.com/events-official"
WPBA_EVENTS_2026 = "https://wpba.com/wpba-2026-events-and-results"
WPBA_EVENTS_2025 = "https://wpba.com/wpba-2025-events-and-results"
WPA_CALENDAR = "https://wpapool.com/calendar-2/"
WPA_EVENTS_CATEGORY = "https://wpapool.com/category/events/"

USER_AGENT = "RankingsBot/1.0 (tournament-history)"
HEADERS = {"User-Agent": USER_AGENT}


def discover_wpba_events(
    html: str,
    base_url: str,
    *,
    include_future: bool = True,
    include_past: bool = True,
) -> List[Dict]:
    """
    Parse WPBA events/results page. Extracts event name, date range, location, event URL,
    and bracket link on the public site (e.g. ``https://digitalpool.com/...``) when present.
    """
    events = []
    today = datetime.now().date()

    # Date range: "Jan 14, 2026 – Jan 18, 2026" or "Jan 14, 2026 &ndash; Jan 18, 2026"
    # Note: [–\-&ndash;] as char class only matches 1 char; &ndash; is 7 chars - use alternation
    date_range_re = re.compile(
        r"([A-Za-z]+\s+\d{1,2},\s+\d{4})\s*(?:–|-|&ndash;)\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        re.IGNORECASE,
    )
    # Event title link: <a href="...">Title</a> - supports absolute and relative URLs
    link_re = re.compile(
        r'<a\s+[^>]*href=["\']((?:https://wpba\.com)?/[^"\']+)["\'][^>]*>([^<]+)</a>',
        re.IGNORECASE,
    )
    # Bracket link: ](https://digitalpool.com/.../bracket) or href="https://digitalpool.com/..."
    external_re = re.compile(
        r'(?:href=["\']|]\()(https://digitalpool\.com/[^"\')]+)["\']?\)?',
        re.IGNORECASE,
    )

    for m in date_range_re.finditer(html):
        start_s, end_s = m.group(1).strip(), m.group(2).strip()
        try:
            start_d = datetime.strptime(start_s, "%b %d, %Y").date()
            end_d = datetime.strptime(end_s, "%b %d, %Y").date()
        except ValueError:
            continue
        if not include_future and end_d >= today:
            continue
        if not include_past and end_d < today:
            continue

        # Block of text around this date (preceding content for event name/link)
        start_pos = max(0, m.start() - 1500)
        block = html[start_pos : m.end() + 800]

        name, event_url = None, None
        for link_m in list(link_re.finditer(block))[-2:]:
            url_cand, name_cand = link_m.group(1), link_m.group(2).strip()
            if "event" in url_cand.lower() or "wpba-20" in url_cand:
                if "format=ical" not in url_cand and "cart" not in url_cand:
                    name = name_cand
                    event_url = urljoin(base_url, url_cand)
                    break
        if not name:
            # Alternative: first <h1> or # Title before the date
            h1 = re.search(r"<h1[^>]*>([^<]+)</h1>", block, re.IGNORECASE)
            if h1:
                name = re.sub(r"<[^>]+>", "", h1.group(1)).strip()
            if not name:
                name = f"WPBA Event {start_d.isoformat()}"

        bracket_url = None
        for dr in external_re.finditer(block):
            bracket_url = dr.group(1).strip()
            if "bracket" in bracket_url.lower() or "tournament" in bracket_url.lower():
                break
            if not bracket_url.endswith("/"):
                bracket_url = bracket_url.rstrip(")'\"")

        location = None
        loc_match = re.search(
            r"(?:Iron City Billiards|Classic Billiards|Raxx Pool Room|[A-Za-z\s]+Billiards?)[^<]*(?:AL|FL|NY|MI|NH|TN|WI)\s*\d{5}",
            block,
        )
        if loc_match:
            location = loc_match.group(0).strip()[:255]
        if not location:
            city = re.search(
                r"((?:Ft\.?|Fort)\s+Lauderdale|Las\s+Vegas|Orlando|Chicago|Birmingham)[^<]*",
                block,
                re.IGNORECASE,
            )
            if city:
                location = city.group(0).strip()[:255]

        events.append({
            "name": (name or "WPBA Event")[:300],
            "start_date": start_d.isoformat(),
            "end_date": end_d.isoformat(),
            "date": end_d.isoformat(),
            "location": location,
            "url": event_url or base_url,
            "bracket_url": bracket_url,
            "association": "WPBA",
            "year": end_d.year,
        })
    return events


def discover_wpa_events(
    html: str,
    base_url: str,
    *,
    include_future: bool = True,
    include_past: bool = True,
) -> List[Dict]:
    """Parse WPA calendar/events for event title, date, and link. Bracket URLs are rarely on the list page."""
    events = []
    today = datetime.now().date()
    date_re = re.compile(
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
    )
    # Match h2 with nested <a> (e.g. <h2 class="bdpp-post-title"><a href="...">Title</a></h2>)
    h2_link_re = re.compile(
        r'<h2[^>]*>\s*<a\s+[^>]*href=["\'](https://wpapool\.com/[^"\']+)["\'][^>]*>([^<]+)</a>\s*</h2>',
        re.IGNORECASE | re.DOTALL,
    )
    # Alternative: any wpapool link with title
    link_re = re.compile(r'<a\s+[^>]*href=["\'](https://wpapool\.com/[^"\']+)["\'][^>]*>([^<]+)</a>')

    for date_m in date_re.finditer(html):
        try:
            dt = datetime.strptime(date_m.group(0), "%B %d, %Y").date()
        except ValueError:
            continue
        if not include_future and dt >= today:
            continue
        if not include_past and dt < today:
            continue
        # Block: look backwards for title/link (before the date), then a bit after
        start_pos = max(0, date_m.start() - 1200)
        block = html[start_pos : date_m.end() + 100]
        title, url = None, base_url
        for m in list(h2_link_re.finditer(block))[-1:]:
            url, title = m.group(1), m.group(2).strip()
            break
        if not title:
            for link_m in list(link_re.finditer(block))[-2:]:
                url_cand, name_cand = link_m.group(1), link_m.group(2).strip()
                if "category" in url_cand or "Events" in name_cand or "News" in name_cand:
                    continue
                title = name_cand
                url = url_cand
                break
        if not title:
            title = f"WPA Event {dt.isoformat()}"
        source = "WPA Women" if "women" in title.lower() or "woman" in title.lower() else "WPA Men"
        events.append({
            "name": title[:300],
            "start_date": dt.isoformat(),
            "end_date": dt.isoformat(),
            "date": dt.isoformat(),
            "location": None,
            "url": url,
            "bracket_url": None,
            "association": source,
            "year": dt.year,
        })
    return events


def fetch_wpba_past_events(include_future: bool = False) -> List[Dict]:
    """Fetch WPBA pages and return past (and optionally future) events with bracket links when available."""
    out = []
    # Try main events-official first (same URL as events_scraper), then year-specific pages
    for url in (WPBA_EVENTS_OFFICIAL, WPBA_EVENTS_2026, WPBA_EVENTS_2025):
        try:
            r = get_with_retry(url, headers=HEADERS, timeout=25, max_retries=3)
            r.raise_for_status()
            items = discover_wpba_events(
                r.text, url, include_future=include_future, include_past=True
            )
            # Dedupe by (name, end_date)
            seen = {(e["name"], e["end_date"]) for e in out}
            for e in items:
                k = (e["name"], e["end_date"])
                if k not in seen:
                    seen.add(k)
                    out.append(e)
        except Exception as exc:
            logger.warning("WPBA discovery %s failed: %s", url[:50], exc)
    return out


def fetch_wpa_past_events(include_future: bool = False) -> List[Dict]:
    """Fetch WPA calendar and return past (and optionally future) events."""
    out = []
    for url in (WPA_CALENDAR, WPA_EVENTS_CATEGORY):
        try:
            r = get_with_retry(url, headers=HEADERS, timeout=25, max_retries=3)
            r.raise_for_status()
            items = discover_wpa_events(
                r.text, url, include_future=include_future, include_past=True
            )
            seen = {(e["name"], e["end_date"]) for e in out}
            for e in items:
                k = (e["name"], e["end_date"])
                if k not in seen:
                    seen.add(k)
                    out.append(e)
        except Exception as exc:
            logger.warning("WPA discovery %s failed: %s", url[:50], exc)
    return out


def discover_past_events(
    wpba: bool = True,
    wpa: bool = True,
    include_future: bool = False,
) -> List[Dict]:
    """Discover past tournament events from WPBA and/or WPA. Optionally include future events."""
    result = []
    if wpba:
        result.extend(fetch_wpba_past_events(include_future=include_future))
    if wpa:
        result.extend(fetch_wpa_past_events(include_future=include_future))
    result.sort(key=lambda x: (x["end_date"], x["name"]), reverse=True)
    return result
