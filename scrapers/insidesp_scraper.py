#!/usr/bin/env python3
"""
Inside Spin (insidesp.in) Tier-1 scraper.

Inside Spin is a global professional **pool** (9/10/8-ball, one-pocket) results +
ratings aggregator (NOT an India/snooker site, despite the .in TLD). See
``docs/MULTI_SOURCE_DATA_INTEGRATION_PLAN.md`` §1b.

Tier 1 = server-rendered listing pages only (no headless browser): each listing
page embeds a clean schema.org ``ItemList`` of the latest/top 100 records in a
``<script type="application/ld+json">`` block. We parse that directly with
``requests`` — fast and robust:

- ``/tournaments`` (≡ ``/events``) -> ``SportsEvent`` items with ``startDate`` /
  ``endDate`` / ``location`` / ``winner`` / Discipline.
- ``/ratings/<discipline>`` -> ``Person`` items with ``nationality`` + Inside
  Spin's own Display Rating + Matches Rated.

Tier 2 (historical depth) uses ``/api/tournaments?beginYear=&endYear=`` plus RSC
``participantRows`` on detail pages — see ``scrapers/insidesp_tier2_scraper.py``.
Bare ``/api/tournaments`` (no year params) returns 401; the SPA passes year range.

Policy: per ``rankings-bot`` rule ``no-automatic-scraping.mdc`` this is
**manual / admin-triggered** only — bounded retries, jittered delay, descriptive
User-Agent. Do not wire into an unattended scheduler.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

INSIDESP_BASE_URL = "https://www.insidesp.in"

# Rating URL slug -> ranking_system suffix used in the `rankings` table
# (InsideSpin_<suffix>; allowed by Alembic migration 056). Enumerated from the
# live /ratings index nav (do not hardcode by guess): per-discipline lists plus
# the cohort "overall" lists (all / women / juniors). 'women' and 'juniors' use
# Discipline=OVERALL on the source (cohort views of the composite rating).
RATING_DISCIPLINES: Dict[str, str] = {
    "9-ball": "9Ball",
    "10-ball": "10Ball",
    "8-ball": "8Ball",
    "one-pocket": "OnePocket",
    "all": "Overall",
    "women": "Women",
    "juniors": "Juniors",
}

_LD_JSON_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S
)


class InsideSpinScraper:
    """Tier-1 scraper for insidesp.in (events + ratings via schema.org JSON-LD)."""

    BASE_URL = INSIDESP_BASE_URL
    REQUEST_TIMEOUT = 30

    def __init__(
        self,
        *,
        min_delay_sec: float = 1.2,
        max_delay_sec: float = 2.6,
        max_retries: int = 3,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "RankingsBot/1.0 (insidesp-tier1; manual)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "gzip",
        })
        self.min_delay_sec = max(0.0, float(min_delay_sec))
        self.max_delay_sec = max(self.min_delay_sec, float(max_delay_sec))
        self.max_retries = max(1, int(max_retries))
        self._last_request_at = 0.0

        # Use the writable, bind-mounted scraped_data/ tree (same convention as
        # externalpool_scraper). Archiving is best-effort: a read-only FS must not
        # abort a scrape.
        self.archive_dir = Path("scraped_data/insidesp")
        self._archive_enabled = True
        try:
            self.archive_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning("Inside Spin: archive dir unavailable (%s); archiving disabled", e)
            self._archive_enabled = False

    # ---- HTTP plumbing ----------------------------------------------------

    def _pace(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_at
        target = random.uniform(self.min_delay_sec, self.max_delay_sec)
        if elapsed < target:
            time.sleep(target - elapsed)
        self._last_request_at = time.monotonic()

    def _fetch(self, path: str) -> str:
        url = path if path.startswith("http") else f"{self.BASE_URL}{path}"
        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self._pace()
                resp = self.session.get(url, timeout=self.REQUEST_TIMEOUT)
                resp.raise_for_status()
                return resp.text
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if attempt >= self.max_retries:
                    break
                backoff = min(8.0, (2 ** (attempt - 1)) + random.random())
                logger.warning(
                    "Inside Spin fetch failed (%s/%s) for %s: %s; retry in %.1fs",
                    attempt, self.max_retries, url, exc, backoff,
                )
                time.sleep(backoff)
        raise RuntimeError(f"Inside Spin fetch failed after retries: {last_err}")

    @staticmethod
    def _extract_itemlist_items(html: str) -> List[Dict[str, Any]]:
        """Return the `item` objects from the first schema.org ItemList block."""
        for block in _LD_JSON_RE.findall(html):
            try:
                data = json.loads(block)
            except (json.JSONDecodeError, ValueError):
                continue
            node = InsideSpinScraper._find_itemlist(data)
            if node is None:
                continue
            items: List[Dict[str, Any]] = []
            for el in node.get("itemListElement") or []:
                if not isinstance(el, dict):
                    continue
                item = el.get("item")
                if isinstance(item, dict):
                    item = dict(item)
                    if el.get("position") is not None and "position" not in item:
                        item["position"] = el.get("position")
                    items.append(item)
            if items:
                return items
        return []

    @staticmethod
    def _find_itemlist(obj: Any) -> Optional[Dict[str, Any]]:
        if isinstance(obj, dict):
            if obj.get("@type") == "ItemList":
                return obj
            for v in obj.values():
                found = InsideSpinScraper._find_itemlist(v)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for v in obj:
                found = InsideSpinScraper._find_itemlist(v)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _prop(item: Dict[str, Any], name: str) -> Optional[str]:
        """Read a schema.org additionalProperty value by name (single dict or list)."""
        ap = item.get("additionalProperty")
        if isinstance(ap, dict):
            ap = [ap]
        if isinstance(ap, list):
            for p in ap:
                if isinstance(p, dict) and str(p.get("name", "")).strip().lower() == name.lower():
                    val = p.get("value")
                    return str(val).strip() if val is not None else None
        return None

    @staticmethod
    def _slug_from_url(url: str) -> Optional[str]:
        if not url:
            return None
        m = re.search(r"/(?:tournaments|events|players)/([^/?#]+)", url)
        return m.group(1) if m else None

    # ---- Events -----------------------------------------------------------

    def scrape_events(self) -> List[Dict[str, Any]]:
        """Latest ~100 events with dates (Tier 1)."""
        logger.info("Inside Spin: scraping events listing")
        html = self._fetch("/tournaments")
        items = self._extract_itemlist_items(html)
        events: List[Dict[str, Any]] = []
        for it in items:
            name = (it.get("name") or "").strip()
            url = (it.get("url") or "").strip()
            if not name:
                continue
            loc = it.get("location")
            location = None
            if isinstance(loc, dict):
                location = (loc.get("name") or "").strip() or None
            elif isinstance(loc, str):
                location = loc.strip() or None
            winner = it.get("winner")
            winner_name = None
            if isinstance(winner, dict):
                winner_name = (winner.get("name") or "").strip() or None
            events.append({
                "name": name,
                "slug": self._slug_from_url(url),
                "url": url,
                "start_date": (it.get("startDate") or "").strip() or None,
                "end_date": (it.get("endDate") or "").strip() or None,
                "location": location,
                "winner": winner_name,
                "discipline": self._prop(it, "Discipline"),
                "source": "insidesp",
            })
        logger.info("Inside Spin: parsed %s events", len(events))
        if events:
            self._archive(events, "events")
        return events

    # ---- Ratings ----------------------------------------------------------

    def scrape_ratings(self, discipline_slug: str) -> List[Dict[str, Any]]:
        """Top ~100 ratings for one discipline (e.g. '9-ball'). Tier 1."""
        if discipline_slug not in RATING_DISCIPLINES:
            logger.warning("Inside Spin: unknown rating discipline %r", discipline_slug)
        logger.info("Inside Spin: scraping ratings/%s", discipline_slug)
        html = self._fetch(f"/ratings/{discipline_slug}")
        items = self._extract_itemlist_items(html)
        rows: List[Dict[str, Any]] = []
        for it in items:
            name = (it.get("name") or "").strip()
            if not name:
                continue
            rating_raw = self._prop(it, "Display Rating") or self._prop(it, "Overall Rating")
            matches_rated = self._prop(it, "Matches Rated")
            try:
                position = int(it.get("position")) if it.get("position") is not None else len(rows) + 1
            except (TypeError, ValueError):
                position = len(rows) + 1
            # `rankings` requires rank>0 and a numeric points column. These are rank
            # lists; the real Inside Spin rating + matches go into source_data.
            nationality = (it.get("nationality") or "").strip() or None
            entry: Dict[str, Any] = {
                "name": name,
                "rank": position,
                "points": 0.0,
                "country": nationality,
                "source": "insidesp",
                "discipline": self._prop(it, "Discipline") or discipline_slug,
            }
            # `country` is governed by the player country-lock policy (Inside Spin is
            # non-authoritative, so it gets nulled/overridden on save). Preserve the
            # raw Inside Spin nationality in source_data so it is never lost.
            if nationality:
                entry["insidesp_nationality"] = nationality
            if rating_raw is not None:
                try:
                    entry["insidesp_rating"] = float(rating_raw)
                except ValueError:
                    entry["insidesp_rating"] = rating_raw
            if matches_rated is not None:
                try:
                    entry["matches_rated"] = int(matches_rated)
                except ValueError:
                    entry["matches_rated"] = matches_rated
            rows.append(entry)
        logger.info("Inside Spin: parsed %s ratings for %s", len(rows), discipline_slug)
        if rows:
            self._archive(rows, f"ratings_{RATING_DISCIPLINES.get(discipline_slug, discipline_slug)}")
        return rows

    def scrape_all_ratings(self) -> Dict[str, List[Dict[str, Any]]]:
        """All disciplines -> {InsideSpin system suffix: rows}. One discipline's
        failure does not abort the others."""
        out: Dict[str, List[Dict[str, Any]]] = {}
        for slug, suffix in RATING_DISCIPLINES.items():
            try:
                rows = self.scrape_ratings(slug)
                if rows:
                    out[suffix] = rows
            except Exception as exc:  # noqa: BLE001
                logger.warning("Inside Spin ratings/%s failed: %s", slug, exc)
        return out

    # ---- archive ----------------------------------------------------------

    def _archive(self, records: List[Dict[str, Any]], data_type: str) -> None:
        if not self._archive_enabled:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        payload = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "scraper": "insidesp_scraper",
                "source": "insidesp_tier1_jsonld",
                "data_type": data_type,
                "base_url": self.BASE_URL,
                "count": len(records),
            },
            "records": records,
        }
        path = self.archive_dir / f"insidesp_{data_type}_{ts}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            logger.info("Inside Spin: archived %s %s to %s", len(records), data_type, path)
        except OSError as e:
            logger.error("Inside Spin: failed to archive %s: %s", data_type, e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    s = InsideSpinScraper()
    evs = s.scrape_events()
    print(f"events: {len(evs)}; sample: {evs[0] if evs else None}")
    ratings = s.scrape_all_ratings()
    for sysname, rows in ratings.items():
        print(f"{sysname}: {len(rows)} rows; sample: {rows[0] if rows else None}")
