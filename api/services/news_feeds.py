"""
RSS/Atom feed helpers for billiards news (WPBA, WPA, AZBilliards).

Shared by the public /api/news route and admin upcoming-event enrichment.
"""

from __future__ import annotations

import html
import logging
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")

DEFAULT_FEEDS: list[tuple[str, str]] = [
    ("AZBilliards", "https://www.azbilliards.com/feed/"),
    ("WPA Pool", "https://wpapool.com/feed/"),
    ("WPBA", "https://wpba.com/feed/"),
]

_USER_AGENT = "RankingsBot-NewsFeeds/1.0"


def parse_feeds_env() -> list[tuple[str, str]]:
    raw = (os.getenv("NEWS_RSS_FEEDS") or "").strip()
    if not raw:
        return list(DEFAULT_FEEDS)
    out: list[tuple[str, str]] = []
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        if "|" in p:
            name, url = p.split("|", 1)
            out.append((name.strip() or "News", url.strip()))
        else:
            out.append(("News", p))
    return out if out else list(DEFAULT_FEEDS)


def strip_summary(text: str | None, max_len: int = 500) -> str:
    if not text:
        return ""
    plain = _TAG_RE.sub(" ", text)
    plain = html.unescape(plain)
    plain = " ".join(plain.split())
    if len(plain) <= max_len:
        return plain
    return plain[: max_len - 1].rsplit(" ", 1)[0] + "…"


def _entry_datetime(entry: Any) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        t = getattr(entry, key, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    for key in ("published", "updated"):
        raw = getattr(entry, key, None)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (TypeError, ValueError):
                pass
    return datetime.min.replace(tzinfo=timezone.utc)


def _parse_feed_bytes(source: str, url: str, content: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        parsed = feedparser.parse(content)
    except Exception as e:
        logger.warning("News RSS parse failed for %s (%s): %s", source, url, e)
        return out

    for entry in getattr(parsed, "entries", []) or []:
        title = getattr(entry, "title", None) or ""
        link = getattr(entry, "link", None) or ""
        if not title or not link:
            continue
        summary = ""
        if getattr(entry, "summary", None):
            summary = strip_summary(str(entry.summary))
        elif getattr(entry, "description", None):
            summary = strip_summary(str(entry.description))

        dt = _entry_datetime(entry)
        published_iso = dt.isoformat() if dt != datetime.min.replace(tzinfo=timezone.utc) else ""

        out.append(
            {
                "title": title.strip(),
                "url": link.strip(),
                "source": source,
                "published": published_iso,
                "summary": summary,
            }
        )
    return out


def fetch_one_feed_sync(client: httpx.Client, source: str, url: str) -> list[dict[str, Any]]:
    try:
        resp = client.get(url, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("News RSS fetch failed for %s (%s): %s", source, url, e)
        return []
    return _parse_feed_bytes(source, url, resp.content)


def fetch_all_feeds_sync(timeout_sec: float = 12.0) -> list[dict[str, Any]]:
    """Blocking fetch for admin refresh jobs (manual-triggered)."""
    feeds = parse_feeds_env()
    timeout = httpx.Timeout(timeout_sec, connect=5.0)
    merged: list[dict[str, Any]] = []
    with httpx.Client(timeout=timeout, headers={"User-Agent": _USER_AGENT}) as client:
        for name, url in feeds:
            merged.extend(fetch_one_feed_sync(client, name, url))

    def sort_key(a: dict[str, Any]) -> datetime:
        p = a.get("published") or ""
        try:
            if p:
                return datetime.fromisoformat(p.replace("Z", "+00:00"))
        except ValueError:
            pass
        return datetime.min.replace(tzinfo=timezone.utc)

    merged.sort(key=sort_key, reverse=True)
    return merged
