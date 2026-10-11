#!/usr/bin/env python3
"""
Digital Pool ("External Pool" / CP) Rankings Scraper.

Source of truth: Digital Pool's public Hasura GraphQL API at
``https://api-nyc.digitalpool.com/v1/graphql`` (the same backend the
digitalpool.com SPA and the tournament harvester use). The legacy REST
``/rankings/*`` shape on ``api.digitalpool.com`` never existed publicly and
timed out — this rewrite targets the real GraphQL "Pro Rankings" data.

Pro Rankings are first-class data on Digital Pool:
- ``pro_world_rankings`` (per-player, per-system, time-series via ``rank_date``)
- ``ranking_systems`` (Fargo / Matchroom / WPA / US Pro Series)
- composite SQL views the public Pro Rankings page renders:
    * ``vw_current_pro_rankings``        (overall composite ``digital_pool_ranking``)
    * ``vw_current_mens_pro_rankings``   (``digital_pool_mens_ranking``)
    * ``vw_current_womens_pro_rankings`` (``digital_pool_womens_ranking``)

These are *rank-position* systems (no per-player "points"), so ``points`` is
returned as ``0.0`` and the real per-system ranks (Fargo/Matchroom/WPA/weighted)
plus the Digital Pool player id are preserved verbatim in ``source_data`` (the
``rankings`` table keeps any non-first-class keys as JSONB). Nothing is invented.

Policy: per ``rankings-bot`` workspace rule ``no-automatic-scraping.mdc`` this is
designed for *manual / admin-triggered* refresh only (rate-limited, bounded
retries). Do not wire it into an unattended scheduler.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Real Digital Pool API (GraphQL/Hasura). See api/services/competitors_import.py
# and scrapers/externalpool_tournament_harvester.py which use the same host.
DIGITALPOOL_GRAPHQL_URL = "https://api-nyc.digitalpool.com/v1/graphql"
DIGITALPOOL_BASE_URL = "https://digitalpool.com"


@dataclass
class CpRanking:
    """A single Digital Pool Pro Rankings entry."""
    rank: int
    player_name: str
    points: float = 0.0
    country: Optional[str] = None
    digitalpool_player_id: Optional[int] = None
    fargo_ranking: Optional[int] = None
    matchroom_ranking: Optional[int] = None
    wpa_ranking: Optional[int] = None


class CpScraper:
    """Scraper for Digital Pool ("External Pool"/CP) Pro Rankings via GraphQL."""

    GRAPHQL_URL = DIGITALPOOL_GRAPHQL_URL
    BASE_URL = DIGITALPOOL_BASE_URL
    REQUEST_TIMEOUT = 30

    # Gender -> (view name, rank field, extra rank fields kept in source_data).
    _RANKING_VIEWS: Dict[str, Dict[str, Any]] = {
        "overall": {
            "view": "vw_current_pro_rankings",
            "rank_field": "digital_pool_ranking",
            "extra_fields": [
                "digital_pool_mens_ranking",
                "digital_pool_womens_ranking",
                "fargo_ranking",
                "matchroom_ranking",
                "wpa_mens_ranking",
                "wpa_womens_ranking",
            ],
        },
        "men": {
            "view": "vw_current_mens_pro_rankings",
            "rank_field": "digital_pool_mens_ranking",
            "extra_fields": [
                "fargo_mens_ranking",
                "wpa_mens_ranking",
                "weighted_fargo_mens_ranking",
                "weighted_wpa_mens_ranking",
            ],
        },
        "women": {
            "view": "vw_current_womens_pro_rankings",
            "rank_field": "digital_pool_womens_ranking",
            "extra_fields": [
                "fargo_womens_ranking",
                "wpa_womens_ranking",
                "weighted_fargo_womens_ranking",
                "weighted_wpa_womens_ranking",
            ],
        },
    }

    # Kept for backward-compat with callers that pass a game_type label.
    GAME_TYPES = {
        "9Ball": "9-ball",
        "10Ball": "10-ball",
        "8Ball": "8-ball",
        "StraitPool": "straight-pool",
        "OnePocket": "one-pocket",
        "BankPool": "bank-pool",
    }

    def __init__(self, api_key: Optional[str] = None,
                 min_delay_sec: float = 1.2, max_delay_sec: float = 2.5,
                 max_retries: int = 3) -> None:
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "RankingsBot/1.0 (digitalpool-pro-rankings)",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip",
        })
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"

        self.min_delay_sec = max(0.0, float(min_delay_sec))
        self.max_delay_sec = max(self.min_delay_sec, float(max_delay_sec))
        self.max_retries = max(1, int(max_retries))
        self._last_request_at = 0.0

        self.scraped_data_dir = Path("scraped_data/externalpool")
        self.scraped_data_dir.mkdir(parents=True, exist_ok=True)

    # ---- GraphQL plumbing -------------------------------------------------

    def _pace(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_at
        target = random.uniform(self.min_delay_sec, self.max_delay_sec)
        if elapsed < target:
            time.sleep(target - elapsed)
        self._last_request_at = time.monotonic()

    def _graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self._pace()
                response = self.session.post(
                    self.GRAPHQL_URL,
                    json={"query": query, "variables": variables or {}},
                    timeout=self.REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("errors"):
                    raise RuntimeError(f"Digital Pool GraphQL errors: {payload['errors'][:1]}")
                return payload.get("data") or {}
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if attempt >= self.max_retries:
                    break
                backoff = min(8.0, (2 ** (attempt - 1)) + random.random())
                logger.warning(
                    "Digital Pool GraphQL failed (%s/%s): %s; retry in %.1fs",
                    attempt, self.max_retries, exc, backoff,
                )
                time.sleep(backoff)
        raise RuntimeError(f"Digital Pool GraphQL request failed after retries: {last_err}")

    # ---- Public API -------------------------------------------------------

    def scrape_rankings(self, game_type: str = "9Ball", gender: Optional[str] = None,
                        region: str = "global", limit: int = 1000) -> List[Dict]:
        """Scrape Digital Pool Pro Rankings.

        **Manual / admin-triggered only** (see module docstring + workspace rule).

        Args:
            game_type: kept for backward compatibility; Pro Rankings are a
                cross-discipline composite, so this only labels the run.
            gender: 'Men'/'Women'/'Mixed' (or None) -> selects the men's,
                women's or overall composite Pro Rankings view.
            region: unused (Digital Pool Pro Rankings are global).
            limit: max rows to return.

        Returns:
            List of ranking dicts: ``{name, rank, points, country, ...}`` where
            extra per-system ranks are preserved (flow into ``rankings.source_data``).
        """
        view_key = self._view_key_for_gender(gender)
        spec = self._RANKING_VIEWS[view_key]
        logger.info(
            "Scraping Digital Pool Pro Rankings (view=%s, label=%s, limit=%s)",
            spec["view"], game_type, limit,
        )

        rows = self._fetch_ranking_view(spec, limit=limit)

        rankings: List[Dict] = []
        for row in rows:
            name = (row.get("name") or "").strip()
            rank_raw = row.get(spec["rank_field"])
            if not name or rank_raw is None:
                continue
            try:
                rank = int(rank_raw)
            except (TypeError, ValueError):
                continue
            if rank <= 0:
                continue

            entry: Dict[str, Any] = {
                "name": name,
                "rank": rank,
                # Pro Rankings are rank-position systems; no per-player points exist.
                "points": 0.0,
                "country": row.get("country"),
                # Extras below are NOT first-class -> persisted in rankings.source_data.
                "digitalpool_player_id": row.get("ranked_player_id"),
                "source": "digitalpool_pro_rankings",
                "ranking_view": spec["view"],
            }
            for fld in spec["extra_fields"]:
                if row.get(fld) is not None:
                    entry[fld] = row[fld]
            rankings.append(entry)

        logger.info("Scraped %s Digital Pool Pro Rankings (%s)", len(rankings), spec["view"])
        if rankings:
            self._save_scraped_data(rankings, view_key, f"{self.BASE_URL}/rankings")
        return rankings

    def _view_key_for_gender(self, gender: Optional[str]) -> str:
        g = (gender or "").strip().lower()
        if g.startswith("m"):
            return "men"
        if g.startswith("w") or g.startswith("f"):
            return "women"
        return "overall"

    def _fetch_ranking_view(self, spec: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        view = spec["view"]
        rank_field = spec["rank_field"]
        fields = ["ranked_player_id", "name", "country", rank_field] + list(spec["extra_fields"])
        # de-dupe field list while preserving order
        seen: set = set()
        field_sel = " ".join(f for f in fields if not (f in seen or seen.add(f)))
        query = f"""
        query ProRankings($limit: Int!) {{
          {view}(order_by: {{ {rank_field}: asc_nulls_last }}, limit: $limit) {{
            {field_sel}
          }}
        }}
        """
        data = self._graphql(query, {"limit": max(1, min(int(limit), 10000))})
        return data.get(view) or []

    # ---- Historical pro_world_rankings time-series -----------------------

    # Stable code -> ranking_system suffix map (single source of truth). Saved
    # in the `rankings` table as ``DigitalPool_<suffix>`` (Alembic 057 allows the
    # prefix). Unknown future codes fall back to a sanitized code (see _pwr_suffix).
    PWR_SYSTEM_SUFFIXES: Dict[str, str] = {
        "FARGO_WORLD_RANKINGS": "FargoWorld",
        "MATCHROOM_WORLD_RANKINGS": "MatchroomWorld9Ball",
        "FARGO_WORLD_MENS_RANKINGS": "FargoWorldMen",
        "FARGO_US_RANKINGS": "FargoUS",
        "US_PRO_SERIES_RANKINGS": "USProSeries",
        "WPA_WORLD_MENS_RANKINGS": "WPAWorldMen",
        "WPA_WORLD_WOMENS_RANKINGS": "WPAWorldWomen",
        "FARGO_WORLD_WOMENS_RANKINGS": "FargoWorldWomen",
    }

    def _pwr_suffix(self, code: Optional[str]) -> str:
        code = (code or "").strip()
        if code in self.PWR_SYSTEM_SUFFIXES:
            return self.PWR_SYSTEM_SUFFIXES[code]
        # Fallback: sanitize the code into a CamelCase-ish token so the
        # DigitalPool_<suffix> constraint (^[A-Za-z0-9_]+$) is satisfied.
        cleaned = code.replace("_RANKINGS", "").replace("RANKINGS", "")
        parts = [p for p in cleaned.replace("-", "_").split("_") if p]
        token = "".join(p.capitalize() for p in parts) or "Unknown"
        return token

    def _fetch_ranking_systems(self) -> List[Dict[str, Any]]:
        query = """
        query RankingSystems {
          ranking_systems(order_by: { id: asc }) {
            id
            code
            display_name
          }
        }
        """
        data = self._graphql(query)
        return data.get("ranking_systems") or []

    def _fetch_pwr_for_system(self, system_id: int, page_size: int) -> List[Dict[str, Any]]:
        """Keyset-paginate the full pro_world_rankings history for one system."""
        query = """
        query Pwr($sid: Int!, $after: Int!, $lim: Int!) {
          pro_world_rankings(
            where: { ranking_system_id: { _eq: $sid }, id: { _gt: $after } }
            order_by: { id: asc }
            limit: $lim
          ) {
            id
            player_id
            player_name
            rank_date
            ranking
          }
        }
        """
        out: List[Dict[str, Any]] = []
        after = 0
        lim = max(1, min(int(page_size), 5000))
        while True:
            data = self._graphql(query, {"sid": int(system_id), "after": after, "lim": lim})
            page = data.get("pro_world_rankings") or []
            if not page:
                break
            out.extend(page)
            after = int(page[-1]["id"])
            if len(page) < lim:
                break
        return out

    def scrape_pro_world_rankings_history(self, page_size: int = 1000) -> Dict[str, Dict[str, Any]]:
        """Scrape the full ``pro_world_rankings`` time-series (historical snapshots).

        **Manual / admin-triggered only.** Digital Pool keeps a sparse history of
        per-system rank-position snapshots (``rank_date``). These are *rank-only*
        systems (no points), so each entry carries ``points=0.0`` and the Digital
        Pool ``player_id`` is preserved in ``source_data``.

        Returns a mapping keyed by ranking_system suffix::

            {
              "WPAWorldMen": {
                "code": "WPA_WORLD_MENS_RANKINGS",
                "display": "WPA World Men's Ranking",
                "snapshots": {
                  "2021-09-30": [ {name, rank, points, ...}, ... ],   # ordered by rank
                  ...
                },
              },
              ...
            }
        """
        systems = self._fetch_ranking_systems()
        logger.info("Digital Pool: %s ranking systems for PWR history", len(systems))
        result: Dict[str, Dict[str, Any]] = {}
        for s in systems:
            sid = s.get("id")
            code = s.get("code")
            display = s.get("display_name") or code
            if sid is None:
                continue
            suffix = self._pwr_suffix(code)
            rows = self._fetch_pwr_for_system(int(sid), page_size)

            snapshots: Dict[str, List[Dict[str, Any]]] = {}
            for r in rows:
                rank_date = r.get("rank_date")
                name = (r.get("player_name") or "").strip()
                ranking = r.get("ranking")
                if not rank_date or not name or ranking is None:
                    continue
                try:
                    rank = int(ranking)
                except (TypeError, ValueError):
                    continue
                if rank <= 0:
                    continue
                entry: Dict[str, Any] = {
                    "name": name,
                    "rank": rank,
                    # Rank-position system; no per-player points exist.
                    "points": 0.0,
                    # Non-first-class -> persisted in rankings.source_data.
                    "digitalpool_player_id": r.get("player_id"),
                    "source": "digitalpool_pro_world_rankings",
                    "ranking_system_code": code,
                    "rank_date": rank_date,
                }
                snapshots.setdefault(rank_date, []).append(entry)

            # Each snapshot must be ordered by rank (position = list index on save).
            for rank_date in snapshots:
                snapshots[rank_date].sort(key=lambda e: e["rank"])

            total = sum(len(v) for v in snapshots.values())
            logger.info(
                "Digital Pool PWR: %s -> DigitalPool_%s (%s snapshots, %s rows)",
                code, suffix, len(snapshots), total,
            )
            result[suffix] = {"code": code, "display": display, "snapshots": snapshots}

        return result

    def scrape_player_profile(self, player_id: str) -> Optional[Dict]:
        """Fetch a Digital Pool player profile by player id (GraphQL ``players_by_pk``)."""
        query = """
        query PlayerProfile($id: bigint!) {
          players_by_pk(id: $id) {
            id
            name
            name_slug
            country
            city
            gender
            fargo_id
            fargo_rating
            fargo_effective_rating
            created_date
            updated_date
          }
        }
        """
        try:
            pid = int(str(player_id))
        except (TypeError, ValueError):
            logger.error("scrape_player_profile: invalid player_id %r", player_id)
            return None

        data = self._graphql(query, {"id": pid})
        profile = data.get("players_by_pk")
        if not profile:
            return None
        return {
            "external_pool_id": profile.get("id"),
            "player_name": profile.get("name"),
            "country": profile.get("country"),
            "city": profile.get("city"),
            "gender": profile.get("gender"),
            "fargo_id": profile.get("fargo_id"),
            "fargo_rating": profile.get("fargo_rating") or profile.get("fargo_effective_rating"),
            "join_date": profile.get("created_date"),
            "last_active": profile.get("updated_date"),
        }

    def fetch_players_by_ids(self, player_ids: List[int], batch_size: int = 100) -> Dict[int, Dict[str, Any]]:
        """Fetch Digital Pool player profiles in batches (GraphQL ``id _in``).

        Returns ``{dp_player_id: {name, country, city, region, gender, fargo_id,
        fargo_rating, fargo_robustness}}``. Used by Fargo enrichment to fill our
        ``players`` SSOT (fill-only). Politeness-paced + retried via ``_graphql``.
        """
        # De-dup + coerce to int, preserving only valid ids.
        ids: List[int] = []
        seen: set = set()
        for pid in player_ids:
            try:
                ipid = int(pid)
            except (TypeError, ValueError):
                continue
            if ipid in seen:
                continue
            seen.add(ipid)
            ids.append(ipid)

        query = """
        query PlayersByIds($ids: [Int!]!) {
          players(where: { id: { _in: $ids } }) {
            id
            name
            country
            city
            gender
            fargo_id
            fargo_rating
            fargo_effective_rating
            fargo_robustness
          }
        }
        """
        out: Dict[int, Dict[str, Any]] = {}
        bsize = max(1, int(batch_size))
        for start in range(0, len(ids), bsize):
            chunk = ids[start:start + bsize]
            data = self._graphql(query, {"ids": chunk})
            for p in (data.get("players") or []):
                pid = p.get("id")
                if pid is None:
                    continue
                out[int(pid)] = {
                    "name": p.get("name"),
                    "country": p.get("country"),
                    "city": p.get("city"),
                    "gender": p.get("gender"),
                    "fargo_id": p.get("fargo_id"),
                    "fargo_rating": p.get("fargo_rating") or p.get("fargo_effective_rating"),
                    "fargo_robustness": p.get("fargo_robustness"),
                }
            logger.info(
                "Digital Pool: fetched %s/%s player profiles (batch %s-%s)",
                len(out), len(ids), start, start + len(chunk),
            )
        return out

    def _save_scraped_data(self, rankings: List[Dict], data_type: str, source_url: str) -> None:
        """Archive scraped rankings to scraped_data/externalpool/ as JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "scraper": "externalpool_scraper",
                "source": "digitalpool_pro_rankings_graphql",
                "data_type": data_type,
                "source_url": source_url,
                "total_rankings": len(rankings),
            },
            "rankings": rankings,
        }
        filepath = self.scraped_data_dir / f"externalpool_{data_type}_{timestamp}.json"
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("Saved Digital Pool %s rankings archive to %s", data_type, filepath)
        except OSError as e:
            logger.error("Failed to write Digital Pool rankings archive %s: %s", filepath, e)

    def get_available_game_types(self) -> List[str]:
        return list(self.GAME_TYPES.keys())

    def get_available_regions(self) -> List[str]:
        # Digital Pool Pro Rankings are global; region is not a filter.
        return ["global"]


# Wrapper classes for backward compatibility (identifiers stay "externalpool"
# per docs/WPA_TOURNAMENT_SSOT.md §5f; the live domain is digitalpool.com).
class ExternalPoolWomenScraper:
    """Women's Digital Pool Pro Rankings."""

    def __init__(self):
        self.scraper = CpScraper()

    def scrape_rankings(self, limit: int = 1000) -> List[Dict]:
        return self.scraper.scrape_rankings("9Ball", gender="Women", limit=limit)

    def scrape_player_profile(self, player_id: str) -> Optional[Dict]:
        return self.scraper.scrape_player_profile(player_id)


class ExternalPoolMenScraper:
    """Men's Digital Pool Pro Rankings."""

    def __init__(self):
        self.scraper = CpScraper()

    def scrape_rankings(self, limit: int = 1000) -> List[Dict]:
        return self.scraper.scrape_rankings("9Ball", gender="Men", limit=limit)

    def scrape_player_profile(self, player_id: str) -> Optional[Dict]:
        return self.scraper.scrape_player_profile(player_id)


# Convenience functions
def scrape_external_pool_9ball(limit: int = 1000) -> List[Dict]:
    return CpScraper().scrape_rankings("9Ball", limit=limit)


def scrape_external_pool_10ball(limit: int = 1000) -> List[Dict]:
    """Digital Pool GraphQL has no 10-ball pro ranking view.

    game_type is only a label on the overall composite. Returning that list
    here stored a copy under Competitors_Pool_10Ball.
    """
    logger.warning(
        "Digital Pool has no 10-ball pro ranking view; not returning the overall composite"
    )
    return []


def scrape_external_pool_8ball(limit: int = 1000) -> List[Dict]:
    """Digital Pool GraphQL has no 8-ball pro ranking view. See 10-ball note."""
    logger.warning(
        "Digital Pool has no 8-ball pro ranking view; not returning the overall composite"
    )
    return []


def scrape_external_pool_women_9ball(limit: int = 1000) -> List[Dict]:
    return CpScraper().scrape_rankings("9Ball", gender="Women", limit=limit)


def scrape_external_pool_men_9ball(limit: int = 1000) -> List[Dict]:
    return CpScraper().scrape_rankings("9Ball", gender="Men", limit=limit)


def scrape_external_pool_mixed_9ball(limit: int = 1000) -> List[Dict]:
    return CpScraper().scrape_rankings("9Ball", gender="Mixed", limit=limit)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Digital Pool (External Pool / CP) Pro Rankings Scraper")
    s = CpScraper()
    print("Game type labels:", s.get_available_game_types())
    try:
        overall = s.scrape_rankings(limit=5)
        print(f"Overall Pro Rankings: {len(overall)} rows")
        if overall:
            print("Sample:", overall[0])
        men = scrape_external_pool_men_9ball(limit=3)
        print(f"Men: {len(men)} rows; sample:", men[0] if men else None)
        women = scrape_external_pool_women_9ball(limit=3)
        print(f"Women: {len(women)} rows; sample:", women[0] if women else None)
    except Exception as e:  # noqa: BLE001
        print(f"Scrape failed: {e}")
