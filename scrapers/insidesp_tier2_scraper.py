#!/usr/bin/env python3
"""
Inside Spin (insidesp.in) Tier-2 historical scraper.

Phase 4 of docs/MULTI_SOURCE_DATA_INTEGRATION_PLAN.md. Tier-1 only exposes the
latest ~100 records via schema.org JSON-LD. Tier-2 uses the same endpoints the
Inside Spin SPA uses:

- ``GET /api/tournaments?beginYear=&endYear=`` — full event catalog (requires
  ``Accept: application/json`` + ``Referer``; bare ``/api/tournaments`` returns 401).
- ``GET /tournaments/{slug}`` — embeds full ``participantRows`` in the Next.js RSC
  payload (parseable with ``requests``, no headless browser).

Operator-triggered only (manual / admin). Politeness: jittered delay between requests.
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
INSIDESP_TOURNAMENTS_REFERER = f"{INSIDESP_BASE_URL}/tournaments"

# Pro / major-tour tokens (conservative; same spirit as DP enumerator).
DEFAULT_PRO_KEYWORDS: List[str] = [
    "wpa", "wpba", "mosconi", "matchroom", "world championship",
    "world pool", "world cup", "world 9-ball", "world 10-ball",
    "us open 9", "us open 10", "predator world", "predator championship",
    "international 9-ball", "international 10-ball", "euro tour", "eurotour",
    "china open", "uk open", "world masters",
]

_PARTICIPANT_ROWS_MARKER = "participantRows"


class InsideSpinTier2Scraper:
    """Tier-2: API catalog + RSC participantRows on detail pages."""

    BASE_URL = INSIDESP_BASE_URL
    REQUEST_TIMEOUT = 45

    def __init__(
        self,
        *,
        min_delay_sec: float = 0.8,
        max_delay_sec: float = 1.8,
        max_retries: int = 3,
        pro_keywords: Optional[List[str]] = None,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "RankingsBot/1.0 (insidesp-tier2; manual)",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        })
        self.min_delay_sec = max(0.0, float(min_delay_sec))
        self.max_delay_sec = max(self.min_delay_sec, float(max_delay_sec))
        self.max_retries = max(1, int(max_retries))
        self._last_request_at = 0.0
        self.pro_keywords = list(pro_keywords or DEFAULT_PRO_KEYWORDS)

        self.archive_dir = Path("scraped_data/insidesp")
        self._archive_enabled = True
        try:
            self.archive_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Inside Spin Tier-2: archive dir unavailable (%s)", exc)
            self._archive_enabled = False

    def _pace(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_at
        target = random.uniform(self.min_delay_sec, self.max_delay_sec)
        if elapsed < target:
            time.sleep(target - elapsed)
        self._last_request_at = time.monotonic()

    def _get_json(self, path: str, *, referer: Optional[str] = None) -> Any:
        url = path if path.startswith("http") else f"{self.BASE_URL}{path}"
        headers = {"Referer": referer or INSIDESP_TOURNAMENTS_REFERER}
        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self._pace()
                resp = self.session.get(url, headers=headers, timeout=self.REQUEST_TIMEOUT)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if attempt >= self.max_retries:
                    break
                backoff = min(8.0, (2 ** (attempt - 1)) + random.random())
                logger.warning(
                    "Inside Spin Tier-2 JSON fetch failed (%s/%s) %s: %s; retry %.1fs",
                    attempt, self.max_retries, url, exc, backoff,
                )
                time.sleep(backoff)
        raise RuntimeError(f"Inside Spin Tier-2 JSON fetch failed: {last_err}")

    def _get_html(self, path: str) -> str:
        url = path if path.startswith("http") else f"{self.BASE_URL}{path}"
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "Referer": INSIDESP_TOURNAMENTS_REFERER,
        }
        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self._pace()
                resp = self.session.get(url, headers=headers, timeout=self.REQUEST_TIMEOUT)
                resp.raise_for_status()
                return resp.text
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if attempt >= self.max_retries:
                    break
                backoff = min(8.0, (2 ** (attempt - 1)) + random.random())
                logger.warning(
                    "Inside Spin Tier-2 HTML fetch failed (%s/%s) %s: %s; retry %.1fs",
                    attempt, self.max_retries, url, exc, backoff,
                )
                time.sleep(backoff)
        raise RuntimeError(f"Inside Spin Tier-2 HTML fetch failed: {last_err}")

    def is_pro_like(self, name: str) -> bool:
        """Match pro/major-tour keywords on word boundaries (avoids NWPA ⊃ WPA false positives)."""
        n = (name or "").lower()
        for kw in self.pro_keywords:
            if re.search(rf"\b{re.escape(kw)}\b", n):
                return True
        return False

    def fetch_tournaments_catalog(
        self,
        begin_year: int,
        end_year: int,
    ) -> List[Dict[str, Any]]:
        """Fetch all tournaments in [begin_year, end_year] from the list API."""
        if begin_year > end_year:
            begin_year, end_year = end_year, begin_year
        path = f"/api/tournaments?beginYear={int(begin_year)}&endYear={int(end_year)}"
        payload = self._get_json(path)
        rows = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            logger.warning("Inside Spin Tier-2: unexpected catalog payload type %s", type(payload))
            return []
        logger.info(
            "Inside Spin Tier-2: catalog %s..%s returned %s events",
            begin_year, end_year, len(rows),
        )
        return rows

    @staticmethod
    def parse_placement(position: Any) -> Optional[int]:
        """Map Inside Spin position strings to integer placement (low bound of ranges)."""
        if position is None:
            return None
        s = str(position).strip()
        if not s:
            return None
        if "-" in s:
            s = s.split("-", 1)[0].strip()
        try:
            val = int(float(s))
            return val if val > 0 else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _decode_flight_chunk(cls, chunk: str) -> str:
        """Decode a Next.js flight string chunk (escaped quotes/backslashes)."""
        try:
            return chunk.encode("utf-8").decode("unicode_escape")
        except UnicodeDecodeError:
            return chunk.replace('\\"', '"').replace("\\\\", "\\")

    def extract_participant_rows_from_html(self, html: str) -> List[Dict[str, Any]]:
        """Parse participantRows from tournament detail RSC payload."""
        if _PARTICIPANT_ROWS_MARKER not in html:
            return []
        key = f'{_PARTICIPANT_ROWS_MARKER}":'
        for chunk in re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S):
            if _PARTICIPANT_ROWS_MARKER not in chunk:
                continue
            decoded = self._decode_flight_chunk(chunk)
            idx = decoded.find(key)
            if idx < 0:
                continue
            rest = decoded[idx + len(key):].lstrip()
            if not rest.startswith("["):
                continue
            try:
                rows, _ = json.JSONDecoder().raw_decode(rest)
                if isinstance(rows, list):
                    return [r for r in rows if isinstance(r, dict)]
            except json.JSONDecodeError:
                continue
        return []

    def fetch_participant_rows(self, name_slug: str) -> List[Dict[str, Any]]:
        """Full placement rows for one event (detail page RSC)."""
        slug = (name_slug or "").strip().lstrip("/")
        if not slug:
            return []
        html = self._get_html(f"/tournaments/{slug}")
        rows = self.extract_participant_rows_from_html(html)
        logger.debug("Inside Spin Tier-2: %s participantRows=%s", slug, len(rows))
        return rows

    def rows_to_results(
        self,
        participant_rows: List[Dict[str, Any]],
        *,
        top_finishers: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Normalize participantRows / top_finishers into tournament_results dicts."""
        out: List[Dict[str, Any]] = []
        seen: set = set()
        for row in participant_rows or []:
            if row.get("is_team_participant"):
                continue
            name = (row.get("operator_name") or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            placement = self.parse_placement(row.get("position"))
            if placement is None:
                continue
            reward = row.get("reward")
            try:
                points = float(reward) if reward not in (None, "") else 0.0
            except (TypeError, ValueError):
                points = 0.0
            out.append({
                "player_name": name,
                "placement": placement,
                "points": points,
                "country": row.get("operator_country"),
                "insidesp_player_slug": row.get("operator_slug") or row.get("participant_slug"),
            })
            seen.add(key)
        if out:
            return out
        # Fallback to podium-only from list API.
        for fin in top_finishers or []:
            name = (fin.get("player_name") or "").strip()
            if not name:
                continue
            placement = self.parse_placement(fin.get("position"))
            if placement is None:
                continue
            try:
                points = float(fin.get("winnings") or 0)
            except (TypeError, ValueError):
                points = 0.0
            out.append({
                "player_name": name,
                "placement": placement,
                "points": points,
                "country": fin.get("player_country"),
            })
        return out

    def archive_catalog(self, rows: List[Dict[str, Any]], label: str) -> Optional[str]:
        if not self._archive_enabled or not rows:
            return None
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.archive_dir / f"insidesp_tier2_catalog_{label}_{ts}.json"
        payload = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "scraper": "insidesp_tier2_scraper",
                "label": label,
                "count": len(rows),
            },
            "events": rows,
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            return str(path)
        except OSError as exc:
            logger.error("Inside Spin Tier-2 archive failed: %s", exc)
            return None
