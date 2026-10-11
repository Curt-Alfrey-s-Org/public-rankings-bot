"""
ExternalPool tournament harvester.

Uses ExternalPool's public GraphQL endpoint to enrich local tournament_history
rows with:
- matched ExternalPool event/tournament metadata
- player placements (tournament_results)
- bracket/match rows (tournament_history_matches)

GraphQL tab coverage (discovery):
    The external pool vendor web app is a SPA backed by Hasura at api-nyc.digitalpool.com/v1/graphql.
    UI tabs (bracket, live scores, matches, schedule, players, stats, performance) load data
    from the same core tables: ``tournament_players``, ``tournament_brackets``, and ``matches``
    (division_id = tournament id). There are no separate public tab-specific queries required
    for full coverage; we persist explicit per-tab *slices* derived from those lists so archives
    and API payloads mirror the site tabs.

    Slug-based entry: ``tournaments(where: {slug: {_eq: $slug}})`` resolves a tournament
    without fuzzy event search (see ``harvest_by_slug``).

Design goals:
- polite scraping cadence (jittered delay + bounded retries)
- deterministic matching from local tournament rows -> ExternalPool events
- idempotent DB writes (upsert results, replace matches for refreshed events)
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from sqlalchemy import text

from database import get_database_manager

try:
    from api.services.ollama_name_resolver import resolve_name_match as _ollama_resolve
    _OLLAMA_AVAILABLE = True
except ImportError:
    _OLLAMA_AVAILABLE = False

logger = logging.getLogger(__name__)

EXTERNALPOOL_GRAPHQL_URL = "https://api-nyc.digitalpool.com/v1/graphql"
EXTERNALPOOL_BASE_URL = "https://digitalpool.com"

# Tuning (override in Docker: -e EXTERNALPOOL_MATCH_MIN_SCORE=0.32)
_DEFAULT_MATCH_MIN_SCORE = 0.35
_DEFAULT_SEARCH_LIMIT = 36

# Match / bracket rows that should appear under "Live scores" (same idea as the external pool site UI).
_LIVE_SCORE_STATUSES = frozenset({"in_progress", "live", "playing"})
# Stopwords for picking a distinctive single-token search (too-common tokens match everything).
_TOKEN_SEARCH_STOPWORDS = frozenset(
    {
        "open",
        "tour",
        "the",
        "and",
        "for",
        "wpa",
        "wpba",
        "women",
        "men",
        "pool",
        "ball",
        "nine",
        "ten",
        "cup",
        "year",
        "mens",
        "womens",
        "boys",
        "girls",
        "u19",
        "u17",
    }
)
# Words that must not, by themselves, accept an External Pool event.
_ACCEPT_STOPWORDS = frozenset(
    {
        "open",
        "championship",
        "championships",
        "world",
        "pool",
        "billiards",
        "wpba",
        "wpa",
        "women",
        "men",
        "womens",
        "mens",
        "the",
        "and",
        "for",
        "tour",
        "ball",
        "presented",
        "stage",
        "final",
        "cup",
        "year",
        "boys",
        "girls",
        "heyball",
        "artistic",
    }
)


@dataclass
class HarvestStats:
    scanned: int = 0
    skipped_existing: int = 0
    matched_events: int = 0
    updated_history_rows: int = 0
    upserted_results: int = 0
    replaced_matches: int = 0
    errors: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "scanned": self.scanned,
            "skipped_existing": self.skipped_existing,
            "matched_events": self.matched_events,
            "updated_history_rows": self.updated_history_rows,
            "upserted_results": self.upserted_results,
            "replaced_matches": self.replaced_matches,
            "errors": self.errors,
        }


class ExternalPoolTournamentHarvester:
    def __init__(
        self,
        *,
        min_delay_sec: float = 1.6,
        max_delay_sec: float = 3.2,
        max_retries: int = 3,
        timeout_sec: int = 25,
        match_min_score: Optional[float] = None,
        search_limit: Optional[int] = None,
    ) -> None:
        self.db = get_database_manager()
        self.min_delay_sec = max(0.5, float(min_delay_sec))
        self.max_delay_sec = max(self.min_delay_sec, float(max_delay_sec))
        self.max_retries = max(1, int(max_retries))
        self.timeout_sec = max(5, int(timeout_sec))
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "RankingsBot/1.0 (externalpool-harvester)",
                "Content-Type": "application/json",
            }
        )
        archive_dir = os.getenv("EXTERNALPOOL_TAB_ARCHIVE_DIR", "/tmp/externalpool_tabs")
        self.payload_dir = Path(archive_dir)
        self.payload_dir.mkdir(parents=True, exist_ok=True)
        self._last_request_at = 0.0
        self._match_min_score = float(
            match_min_score
            if match_min_score is not None
            else os.getenv("EXTERNALPOOL_MATCH_MIN_SCORE", str(_DEFAULT_MATCH_MIN_SCORE))
        )
        self._search_limit = int(
            search_limit
            if search_limit is not None
            else os.getenv("EXTERNALPOOL_SEARCH_LIMIT", str(_DEFAULT_SEARCH_LIMIT))
        )

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
                    EXTERNALPOOL_GRAPHQL_URL,
                    json={"query": query, "variables": variables or {}},
                    timeout=self.timeout_sec,
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("errors"):
                    raise RuntimeError(f"GraphQL errors: {payload['errors'][:1]}")
                return payload.get("data") or {}
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if attempt >= self.max_retries:
                    break
                backoff = min(8.0, (2 ** (attempt - 1)) + random.random())
                logger.warning("ExternalPool request failed (%s/%s): %s; retry in %.1fs", attempt, self.max_retries, exc, backoff)
                time.sleep(backoff)
        raise RuntimeError(f"ExternalPool GraphQL request failed after retries: {last_err}")

    @staticmethod
    def _status_lower(row: Dict[str, Any]) -> str:
        return str(row.get("status") or "").lower().replace(" ", "_")

    @staticmethod
    def _sched_sort_key(row: Dict[str, Any]) -> str:
        return str(row.get("scheduled_time") or row.get("start_date_time") or row.get("start_time") or "")

    @classmethod
    def build_tab_views_from_graphql(
        cls,
        players: List[Dict[str, Any]],
        brackets: List[Dict[str, Any]],
        matches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build explicit tab-shaped payloads from the same GraphQL lists the SPA uses.
        Keys align with the external pool site UI: schedule, live scores, stats, performance.
        """
        players = players or []
        brackets = brackets or []
        matches = matches or []

        br_sched = sorted(
            [b for b in brackets if cls._sched_sort_key(b)],
            key=cls._sched_sort_key,
        )
        mt_sched = sorted(
            [m for m in matches if cls._sched_sort_key(m)],
            key=cls._sched_sort_key,
        )
        tab_schedule: Dict[str, Any] = {
            "bracket_rows": br_sched,
            "match_rows": mt_sched,
            "source": "graphql_tournament_brackets_matches_derived",
        }

        br_live = [
            dict(b, _tab_source="bracket")
            for b in brackets
            if cls._status_lower(b) in _LIVE_SCORE_STATUSES
        ]
        mt_live = [
            dict(m, _tab_source="match")
            for m in matches
            if cls._status_lower(m) in _LIVE_SCORE_STATUSES
        ]
        tab_live_scores: Dict[str, Any] = {
            "bracket_matches": br_live,
            "matches": mt_live,
            "source": "graphql_tournament_brackets_matches_derived",
        }

        tab_stats = [
            p
            for p in players
            if p.get("fargo_robustness") is not None
            or p.get("skill_level") not in (None, "")
            or p.get("points") is not None
            or p.get("fargo_id") is not None
        ]
        if not tab_stats:
            tab_stats = list(players)

        perf_matches = [
            dict(m, _tab_source="match")
            for m in matches
            if m.get("player_score") is not None or m.get("opponent_score") is not None
        ]
        perf_brackets = [
            dict(b, _tab_source="bracket")
            for b in brackets
            if b.get("challenger1_score") is not None or b.get("challenger2_score") is not None
        ]
        tab_performance: Dict[str, Any] = {
            "matches": perf_matches,
            "bracket_matches": perf_brackets,
            "source": "graphql_tournament_brackets_matches_derived",
        }

        return {
            "tab_schedule": tab_schedule,
            "tab_live_scores": tab_live_scores,
            "tab_stats": tab_stats,
            "tab_performance": tab_performance,
            "graphql_tabs": {
                "note": (
                    "Derived slices from tournament_players, tournament_brackets, matches; "
                    "mirrors the external pool vendor SPA tab content without extra tab-specific queries."
                ),
                "version": 1,
            },
        }


    @staticmethod
    def _name_years(value: str) -> set:
        return set(re.findall(r"20\d{2}", value or ""))

    @classmethod
    def _distinctive_tokens(cls, value: str) -> List[str]:
        raw = re.sub(r"[^a-z0-9]+", " ", (value or "").lower())
        out: List[str] = []
        seen: set = set()
        for part in raw.split():
            if len(part) < 3 or part in _ACCEPT_STOPWORDS or re.fullmatch(r"20\d{2}", part):
                continue
            if part not in seen:
                seen.add(part)
                out.append(part)
        return out

    @classmethod
    def _token_in_name(cls, token: str, other: str) -> bool:
        words = re.sub(r"[^a-z0-9]+", " ", (other or "").lower()).split()
        if token in words:
            return True
        if len(token) >= 5:
            return any(word.startswith(token) for word in words)
        return False

    @classmethod
    def _event_match_allowed(cls, local_name: str, event_name: str) -> bool:
        """Year agreement plus one distinctive local word in the remote name."""
        local_years = cls._name_years(local_name)
        event_years = cls._name_years(event_name)
        if local_years and event_years and local_years.isdisjoint(event_years):
            return False
        tokens = cls._distinctive_tokens(local_name)
        if not tokens:
            return False
        return any(cls._token_in_name(tok, event_name) for tok in tokens)

    def _event_days_apart(self, local_date: Optional[date], event: Dict[str, Any]) -> Optional[int]:
        if not local_date or not event.get("start_date_time"):
            return None
        try:
            start_dt = datetime.fromisoformat(str(event["start_date_time"]).replace("Z", "+00:00")).date()
        except Exception:  # noqa: BLE001
            return None
        return abs((start_dt - local_date).days)

    @staticmethod
    def _norm_name(value: str) -> str:
        v = (value or "").lower()
        v = re.sub(r"\b(wpba|wpa|women|men|heyball|artistic|final stage|stage)\b", " ", v)
        v = re.sub(r"\b(20\d{2})\b", " ", v)
        v = re.sub(r"[^a-z0-9]+", " ", v)
        return re.sub(r"\s+", " ", v).strip()

    @classmethod
    def _significant_tokens(cls, norm: str) -> List[str]:
        """Longest-first tokens for broader ilike matching (e.g. 'heyball' between city and 'open')."""
        parts = [p for p in (norm or "").split() if len(p) >= 3]
        scored: List[Tuple[int, str]] = []
        for p in parts:
            if p in _TOKEN_SEARCH_STOPWORDS and len(p) < 6:
                continue
            scored.append((len(p), p))
        scored.sort(key=lambda x: (-x[0], x[1]))
        out: List[str] = []
        seen: set = set()
        for _ln, tok in scored:
            if tok not in seen:
                seen.add(tok)
                out.append(tok)
        if not out and parts:
            out = list(dict.fromkeys(parts))[:5]
        return out[:5]

    @staticmethod
    def _token_jaccard(norm_a: str, norm_b: str) -> float:
        ta = set((norm_a or "").split())
        tb = set((norm_b or "").split())
        if not ta or not tb:
            return 0.0
        inter = ta & tb
        union = ta | tb
        return len(inter) / len(union) if union else 0.0

    def _event_score(self, local_name: str, local_date: Optional[date], event: Dict[str, Any]) -> float:
        event_name = event.get("name") or ""
        n_loc = self._norm_name(local_name)
        n_ev = self._norm_name(event_name)
        name_ratio = SequenceMatcher(None, n_loc, n_ev).ratio()
        jacc = self._token_jaccard(n_loc, n_ev)
        # Blend: fuzzy string + shared tokens (helps when word order differs).
        name_score = min(1.0, 0.72 * name_ratio + 0.28 * jacc)
        # Date is a gate in _best_event_match, not a bonus that can beat a better name.
        return (0.90 * name_score) + (0.10 * jacc)

    def _search_events(
        self,
        *,
        name_pattern: str,
        start_window: date,
        end_window: date,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        lim = int(limit if limit is not None else self._search_limit)
        query = """
        query SearchEvents($namePattern: String!, $startDate: timestamptz!, $endDate: timestamptz!, $limit: Int!) {
          events(
            where: {
              _and: [
                { name: { _ilike: $namePattern } }
                { start_date_time: { _gte: $startDate } }
                { start_date_time: { _lte: $endDate } }
              ]
            }
            order_by: [{ start_date_time: desc }]
            limit: $limit
          ) {
            id
            name
            slug
            start_date_time
            end_date_time
            location
            tournaments_aggregate { aggregate { count } }
          }
        }
        """
        data = self._graphql(
            query,
            {
                "namePattern": name_pattern,
                "startDate": f"{start_window.isoformat()}T00:00:00+00:00",
                "endDate": f"{end_window.isoformat()}T23:59:59+00:00",
                "limit": max(8, min(lim, 80)),
            },
        )
        return data.get("events") or []

    def _gather_event_candidates(self, local_name: str, local_date: Optional[date]) -> List[Dict[str, Any]]:
        """
        Multi-stage search to maximize recall without exploding GraphQL calls:

        - Patterns: full normalized title, then longest distinctive tokens (ilike ``%token%``).
        - Date: try ±45d for all patterns first; if still few hits, widen to ±180d, ±400d, then calendar year.

        Dedupes by event id.
        """
        norm = self._norm_name(local_name)
        tokens = self._significant_tokens(norm)
        raw_patterns: List[str] = []
        if norm and len(norm) >= 3:
            raw_patterns.append(f"%{norm.replace(' ', '%')}%")
        for tok in tokens[:4]:
            if len(tok) >= 3:
                raw_patterns.append(f"%{tok}%")

        seen_p: set = set()
        uniq_patterns: List[str] = []
        for p in raw_patterns:
            if p not in seen_p and len(p) >= 5:
                seen_p.add(p)
                uniq_patterns.append(p)

        if not uniq_patterns:
            return []

        seen_ids: Dict[int, Dict[str, Any]] = {}
        max_candidates = max(self._search_limit, 48)

        def merge(rows: List[Dict[str, Any]]) -> None:
            for e in rows:
                eid = e.get("id")
                if eid is None:
                    continue
                iid = int(eid)
                if iid not in seen_ids:
                    seen_ids[iid] = e

        if not local_date:
            today = date.today()
            sw, ew = today - timedelta(days=3650), today + timedelta(days=365)
            for pattern in uniq_patterns[:4]:
                merge(self._search_events(name_pattern=pattern, start_window=sw, end_window=ew))
            return list(seen_ids.values())

        def window_for_stage(stage: int) -> Tuple[date, date]:
            if stage == 0:
                return local_date - timedelta(days=45), local_date + timedelta(days=45)
            if stage == 1:
                return local_date - timedelta(days=180), local_date + timedelta(days=180)
            if stage == 2:
                return local_date - timedelta(days=400), local_date + timedelta(days=400)
            y = local_date.year
            return date(y, 1, 1), date(y, 12, 31)

        # Widen date range only until we have enough rows to rank, or stages exhausted.
        for stage in range(4):
            sw, ew = window_for_stage(stage)
            for pattern in uniq_patterns[:4]:
                if len(seen_ids) >= max_candidates:
                    break
                merge(self._search_events(name_pattern=pattern, start_window=sw, end_window=ew))
            if len(seen_ids) >= 30:
                break

        return list(seen_ids.values())

    def _fetch_event_tournaments(self, event_id: int) -> Dict[str, Any]:
        query = """
        query EventDetails($id: Int!) {
          events_by_pk(id: $id) {
            id
            name
            slug
            start_date_time
            end_date_time
            location
            tournaments(order_by: [{ id: asc }]) {
              id
              name
              slug
              description
              status
              draw_type
              tournament_type
              game_type
              race_to
              winners_race_to
              losers_race_to
              handicapped
              handicap_format
              max_players
              entry_fee
              added_money
              rating_system
              rule_format
              progress
              participant_times_played
              start_date_time
              end_date_time
              current_round
              tournament_players_aggregate { aggregate { count } }
              tournament_brackets_aggregate { aggregate { count } }
            }
          }
        }
        """
        data = self._graphql(query, {"id": int(event_id)})
        return data.get("events_by_pk") or {}

    def _fetch_tournament_players(self, tournament_id: int, limit: int = 512) -> List[Dict[str, Any]]:
        query = """
        query TournamentPlayers($tournamentId: Int!, $limit: Int!) {
          tournament_players(
            where: { tournament_id: { _eq: $tournamentId }, place: { _is_null: false } }
            order_by: [{ place: asc }, { name: asc }]
            limit: $limit
          ) {
            name
            place
            points
            seed
            status
            current_round
            race_to
            fargo_id
            fargo_robustness
            skill_level
            is_advancing
            is_eliminated
            player_id
          }
        }
        """
        data = self._graphql(query, {"tournamentId": int(tournament_id), "limit": int(limit)})
        return data.get("tournament_players") or []

    def _fetch_tournament_brackets(self, tournament_id: int, limit: int = 1200) -> List[Dict[str, Any]]:
        query = """
        query TournamentBrackets($tournamentId: Int!, $limit: Int!) {
          tournament_brackets(
            where: { tournament_id: { _eq: $tournamentId } }
            order_by: [{ stage_number: asc }, { round: asc }, { match_number: asc }]
            limit: $limit
          ) {
            id
            match_id
            stage_number
            round
            match_number
            table_name
            scheduled_time
            start_time
            end_time
            duration
            status
            progress
            challenger1_name
            challenger1_score
            challenger1_is_winner
            challenger1_country
            challenger1_seed
            challenger1_race_to
            challenger2_name
            challenger2_score
            challenger2_is_winner
            challenger2_country
            challenger2_seed
            challenger2_race_to
          }
        }
        """
        data = self._graphql(query, {"tournamentId": int(tournament_id), "limit": int(limit)})
        return data.get("tournament_brackets") or []

    def _fetch_tournament_matches(self, tournament_id: int, limit: int = 2000) -> List[Dict[str, Any]]:
        query = """
        query TournamentMatches($tournamentId: Int!, $limit: Int!) {
          matches(
            where: { division_id: { _eq: $tournamentId } }
            order_by: [{ scheduled_time: asc }, { match_number: asc }]
            limit: $limit
          ) {
            id
            match_number
            match_type
            status
            progress
            table_name
            race_to
            scheduled_time
            start_date_time
            end_date_time
            duration
            player_name
            opponent_name
            player_score
            opponent_score
            player_fargo
            opponent_fargo
          }
        }
        """
        data = self._graphql(query, {"tournamentId": int(tournament_id), "limit": int(limit)})
        return data.get("matches") or []

    def _fetch_tournament_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Resolve a single tournament row by public URL slug (e.g. 2026-wpba-classics-players-championship)."""
        query = """
        query TournamentBySlug($slug: String!) {
          tournaments(where: {slug: {_eq: $slug}}, limit: 1) {
            id
            name
            slug
            description
            status
            draw_type
            tournament_type
            game_type
            race_to
            winners_race_to
            losers_race_to
            handicapped
            handicap_format
            max_players
            entry_fee
            added_money
            rating_system
            rule_format
            progress
            participant_times_played
            start_date_time
            end_date_time
            current_round
            event_id
            tournament_players_aggregate { aggregate { count } }
            tournament_brackets_aggregate { aggregate { count } }
          }
        }
        """
        data = self._graphql(query, {"slug": (slug or "").strip()})
        rows = data.get("tournaments") or []
        return rows[0] if rows else None

    def _fetch_event_by_pk(self, event_id: int) -> Dict[str, Any]:
        query = """
        query EventByPk($id: Int!) {
          events_by_pk(id: $id) {
            id
            name
            slug
            start_date_time
            end_date_time
            location
          }
        }
        """
        data = self._graphql(query, {"id": int(event_id)})
        return data.get("events_by_pk") or {}

    def _load_local_tournament_row(self, tournament_id: str) -> Optional[Dict[str, Any]]:
        with self.db.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT tournament_id, name, date, association, bracket_url
                    FROM tournament_history
                    WHERE tournament_id = :tournament_id
                    LIMIT 1
                    """
                ),
                {"tournament_id": tournament_id},
            ).mappings().first()
        if not row:
            return None
        return dict(row)

    def _iter_local_tournaments(self, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        query = """
            SELECT tournament_id, name, date, association, bracket_url
            FROM tournament_history
            WHERE date IS NOT NULL
              AND name IS NOT NULL
              AND COALESCE(status, 'completed') = 'completed'
            ORDER BY date DESC, tournament_id DESC
        """
        if limit:
            query += " LIMIT :limit"
        with self.db.engine.connect() as conn:
            rows = conn.execute(text(query), {"limit": int(limit)} if limit else {}).fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "tournament_id": r[0],
                    "name": r[1],
                    "date": r[2],
                    "association": r[3],
                    "bracket_url": r[4],
                }
            )
        return out

    def _best_event_match(self, local_tournament: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        candidates = self._gather_event_candidates(
            local_tournament["name"],
            local_tournament.get("date"),
        )
        if not candidates:
            return None
        scored = sorted(
            (
                (self._event_score(local_tournament["name"], local_tournament.get("date"), e), e)
                for e in candidates
            ),
            key=lambda x: x[0],
            reverse=True,
        )
        top_score, top_event = scored[0]
        min_score = max(0.25, min(0.55, self._match_min_score))
        if not self._event_match_allowed(local_tournament.get("name") or "", top_event.get("name") or ""):
            logger.info(
                "External Pool match rejected %s <-> %s (token or year) score=%.3f",
                local_tournament.get("tournament_id"),
                top_event.get("name"),
                top_score,
            )
            return None
        days_apart = self._event_days_apart(local_tournament.get("date"), top_event)
        if days_apart is not None and days_apart > 120:
            logger.info(
                "External Pool match rejected %s <-> %s (date %s days) score=%.3f",
                local_tournament.get("tournament_id"),
                top_event.get("name"),
                days_apart,
                top_score,
            )
            return None
        if top_score < min_score:
            # LLM arbitration for near-miss scores (within 30% of threshold)
            if _OLLAMA_AVAILABLE and top_score >= min_score * 0.7:
                try:
                    import asyncio
                    ctx = {"system_a": "local_db", "system_b": "externalpool"}
                    loop = asyncio.new_event_loop()
                    try:
                        result = loop.run_until_complete(
                            _ollama_resolve(
                                local_tournament["name"],
                                top_event.get("name", ""),
                                context=ctx,
                            )
                        )
                    finally:
                        loop.close()
                    if result and result.is_confident_match:
                        logger.info(
                            "LLM confirmed tournament match: '%s' <-> '%s' (score=%.3f, llm_conf=%.2f)",
                            local_tournament["name"],
                            top_event.get("name", ""),
                            top_score,
                            result.confidence,
                        )
                        return top_event
                except Exception as e:
                    logger.debug("LLM tournament match failed: %s", e)

            logger.debug(
                "External Pool match rejected %s score=%.3f < min=%.3f (candidates=%s)",
                local_tournament.get("tournament_id"),
                top_score,
                min_score,
                len(candidates),
            )
            return None
        return top_event

    @staticmethod
    def _preserve_local_tournament_results(tournament_id: str) -> bool:
        """
        WPBA PDF pipeline writes tournament_results under wpba_evt_* ids from rolling-column points.
        Do not replace those placements/points with External Pool GraphQL data (different meaning).
        Still enrich URLs, raw tab JSON, bracket/match rows.
        """
        return str(tournament_id or "").startswith("wpba_evt_")

    def _upsert_enriched_tournament(
        self,
        *,
        local_tournament: Dict[str, Any],
        event: Dict[str, Any],
        tournament: Dict[str, Any],
        players: List[Dict[str, Any]],
        bracket_rows: List[Dict[str, Any]],
        tab_matches: List[Dict[str, Any]],
    ) -> Tuple[int, int, int]:
        updated_history = 0
        upserted_results = 0
        replaced_matches = 0
        preserve_results = self._preserve_local_tournament_results(local_tournament.get("tournament_id") or "")
        event_url = f"{EXTERNALPOOL_BASE_URL}/events/{event.get('slug')}" if event.get("slug") else None
        bracket_url = f"{EXTERNALPOOL_BASE_URL}/tournaments/{tournament.get('slug')}/viewer" if tournament.get("slug") else None

        with self.db.engine.begin() as conn:
            res = conn.execute(
                text(
                    """
                    UPDATE tournament_history
                    SET source_url = COALESCE(:source_url, source_url),
                        bracket_url = COALESCE(:bracket_url, bracket_url),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE tournament_id = :tournament_id
                    """
                ),
                {
                    "source_url": event_url,
                    "bracket_url": bracket_url,
                    "tournament_id": local_tournament["tournament_id"],
                },
            )
            updated_history = int(res.rowcount or 0)

            if preserve_results:
                logger.info(
                    "Preserving WPBA PDF tournament_results for %s; skipping External Pool player points/placements",
                    local_tournament.get("tournament_id"),
                )

            if not preserve_results:
                for p in players:
                    name = (p.get("name") or "").strip()
                    if not name:
                        continue
                    try:
                        place = int(str(p.get("place")))
                    except (TypeError, ValueError):
                        continue
                    points_raw = p.get("points")
                    try:
                        points = float(points_raw) if points_raw is not None else 0.0
                    except (TypeError, ValueError):
                        points = 0.0
                    # Optional Digital Pool field enrichments (Alembic 061+)
                    seed_raw = p.get("seed")
                    try:
                        seed = int(seed_raw) if seed_raw is not None else None
                    except (TypeError, ValueError):
                        seed = None
                    race_raw = p.get("race_to") or p.get("raceTo")
                    try:
                        race_to = int(race_raw) if race_raw is not None else None
                    except (TypeError, ValueError):
                        race_to = None
                    current_round = p.get("current_round") or p.get("currentRound") or p.get("round")
                    if current_round is not None:
                        current_round = str(current_round)[:128]
                    player_status = p.get("status") or p.get("player_status")
                    if player_status is not None:
                        player_status = str(player_status)[:64]
                    is_elim = p.get("is_eliminated")
                    if is_elim is None:
                        is_elim = p.get("isEliminated")
                    if isinstance(is_elim, str):
                        is_elim = is_elim.lower() in ("1", "true", "yes", "y")
                    elif is_elim is not None:
                        is_elim = bool(is_elim)

                    try:
                        conn.execute(
                            text(
                                """
                                INSERT INTO tournament_results (
                                    tournament_id, player_name, placement, points,
                                    seed, race_to, current_round, player_status, is_eliminated
                                )
                                VALUES (
                                    :tournament_id, :player_name, :placement, :points,
                                    :seed, :race_to, :current_round, :player_status, :is_eliminated
                                )
                                ON CONFLICT (tournament_id, player_name) DO UPDATE SET
                                  placement = EXCLUDED.placement,
                                  points = EXCLUDED.points,
                                  seed = COALESCE(EXCLUDED.seed, tournament_results.seed),
                                  race_to = COALESCE(EXCLUDED.race_to, tournament_results.race_to),
                                  current_round = COALESCE(EXCLUDED.current_round, tournament_results.current_round),
                                  player_status = COALESCE(EXCLUDED.player_status, tournament_results.player_status),
                                  is_eliminated = COALESCE(EXCLUDED.is_eliminated, tournament_results.is_eliminated)
                                """
                            ),
                            {
                                "tournament_id": local_tournament["tournament_id"],
                                "player_name": name[:255],
                                "placement": place,
                                "points": points,
                                "seed": seed,
                                "race_to": race_to,
                                "current_round": current_round,
                                "player_status": player_status,
                                "is_eliminated": is_elim,
                            },
                        )
                    except Exception:
                        # Pre-061 schema fallback
                        conn.execute(
                            text(
                                """
                                INSERT INTO tournament_results (tournament_id, player_name, placement, points)
                                VALUES (:tournament_id, :player_name, :placement, :points)
                                ON CONFLICT (tournament_id, player_name) DO UPDATE SET
                                  placement = EXCLUDED.placement,
                                  points = EXCLUDED.points
                                """
                            ),
                            {
                                "tournament_id": local_tournament["tournament_id"],
                                "player_name": name[:255],
                                "placement": place,
                                "points": points,
                            },
                        )
                    upserted_results += 1

            # Replace old match rows for deterministic refresh.
            conn.execute(
                text("DELETE FROM tournament_history_matches WHERE tournament_id = :tournament_id"),
                {"tournament_id": local_tournament["tournament_id"]},
            )
            matches_by_id: Dict[str, Dict[str, Any]] = {}
            for m in tab_matches:
                mid = m.get("id")
                if mid is not None:
                    matches_by_id[str(mid)] = m
            for b in bracket_rows:
                p1 = (b.get("challenger1_name") or "").strip()
                p2 = (b.get("challenger2_name") or "").strip()
                if not p1 or not p2:
                    continue
                s1 = b.get("challenger1_score")
                s2 = b.get("challenger2_score")
                winner_name = None
                if bool(b.get("challenger1_is_winner")):
                    winner_name = p1
                elif bool(b.get("challenger2_is_winner")):
                    winner_name = p2
                round_num = f"S{b.get('stage_number')}-R{b.get('round')}"
                match_ref = b.get("match_id") or b.get("id")
                tab_match = matches_by_id.get(str(match_ref)) if match_ref is not None else None
                notes = (
                    f"externalpool_match_id={match_ref};"
                    f"table={b.get('table_name') or ''};"
                    f"status={b.get('status') or (tab_match or {}).get('status') or ''};"
                    f"scheduled={b.get('scheduled_time') or (tab_match or {}).get('scheduled_time') or ''};"
                    f"duration={b.get('duration') or (tab_match or {}).get('duration') or ''}"
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO tournament_history_matches
                        (tournament_id, operator_name, player2_name, operator_score, player2_score,
                         winner_name, round_num, match_num, notes)
                        VALUES
                        (:tournament_id, :p1, :p2, :s1, :s2, :winner_name, :round_num, :match_num, :notes)
                        """
                    ),
                    {
                        "tournament_id": local_tournament["tournament_id"],
                        "p1": p1[:255],
                        "p2": p2[:255],
                        "s1": int(s1) if isinstance(s1, (int, float)) else None,
                        "s2": int(s2) if isinstance(s2, (int, float)) else None,
                        "winner_name": winner_name[:255] if winner_name else None,
                        "round_num": round_num[:128],
                        "match_num": int(b["match_number"]) if b.get("match_number") is not None else None,
                        "notes": notes[:1000],
                    },
                )
                replaced_matches += 1

        return updated_history, upserted_results, replaced_matches

    @staticmethod
    def _archive_filename_prefix(
        local_tournament: Dict[str, Any],
        remote_id: int,
        slug: Optional[str] = None,
    ) -> str:
        """Filesystem-safe prefix for JSON archives (local id, or slug_, or externalpool_)."""
        tid = local_tournament.get("tournament_id")
        if tid:
            return str(tid)
        if slug:
            safe = re.sub(r"[^\w\-.]+", "_", slug).strip("_")[:120]
            return f"slug_{safe}" if safe else f"slug_{remote_id}"
        return f"externalpool_{remote_id}"

    def _persist_raw_tab_payload(
        self,
        *,
        local_tournament: Dict[str, Any],
        event: Dict[str, Any],
        tournament: Dict[str, Any],
        players: List[Dict[str, Any]],
        bracket_rows: List[Dict[str, Any]],
        tab_matches: List[Dict[str, Any]],
        slug: Optional[str] = None,
    ) -> Path:
        tab_views = self.build_tab_views_from_graphql(players, bracket_rows, tab_matches)
        payload: Dict[str, Any] = {
            "captured_at": datetime.utcnow().isoformat() + "Z",
            "local_tournament": local_tournament,
            "event_overview": event,
            "tournament_overview": tournament,
            "players": players,
            "brackets": bracket_rows,
            "matches": tab_matches,
            **tab_views,
        }
        if slug:
            payload["externalpool_slug"] = slug
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        rid = int(tournament.get("id") or 0)
        prefix = self._archive_filename_prefix(local_tournament, rid, slug=slug)
        fname = f"{prefix}_{rid}_{ts}.json"
        out = self.payload_dir / fname
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return out


    def _choose_remote_tournament(self, local_name: str, tournaments: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Division whose name passes the same token and year checks as the event."""
        named = [
            row for row in tournaments
            if self._event_match_allowed(local_name, row.get("name") or "")
        ]
        if not named:
            return None

        def sort_key(row: Dict[str, Any]) -> Tuple[int, int, int]:
            status = str(row.get("status") or "").upper()
            brackets = (row.get("tournament_brackets_aggregate") or {}).get("aggregate", {}).get("count") or 0
            players = (row.get("tournament_players_aggregate") or {}).get("aggregate", {}).get("count") or 0
            return (0 if status == "COMPLETED" else 1, -int(brackets), -int(players))

        named.sort(key=sort_key)
        return named[0]

    def harvest(
        self,
        *,
        limit: Optional[int] = None,
        force: bool = False,
        skip_if_bracket_url_exists: bool = True,
    ) -> Dict[str, int]:
        stats = HarvestStats()
        tournaments = self._iter_local_tournaments(limit=limit)
        logger.info("ExternalPool harvester: processing %s tournaments", len(tournaments))
        for t in tournaments:
            stats.scanned += 1
            try:
                existing_bracket = (t.get("bracket_url") or "").strip().lower()
                if (
                    not force
                    and skip_if_bracket_url_exists
                    and existing_bracket
                    and "digitalpool.com" in existing_bracket
                ):
                    stats.skipped_existing += 1
                    continue

                matched_event = self._best_event_match(t)
                if not matched_event:
                    continue
                event_details = self._fetch_event_tournaments(int(matched_event["id"]))
                tournaments_remote = event_details.get("tournaments") or []
                chosen = self._choose_remote_tournament(t.get("name") or "", tournaments_remote)
                if not chosen:
                    logger.info(
                        "External Pool event %s has no division name match for %s",
                        matched_event.get("slug") or matched_event.get("id"),
                        t.get("tournament_id"),
                    )
                    continue
                stats.matched_events += 1
                tid = int(chosen["id"])
                players = self._fetch_tournament_players(tid)
                brackets = self._fetch_tournament_brackets(tid)
                tab_matches = self._fetch_tournament_matches(tid)
                self._persist_raw_tab_payload(
                    local_tournament=t,
                    event=event_details or matched_event,
                    tournament=chosen,
                    players=players,
                    bracket_rows=brackets,
                    tab_matches=tab_matches,
                )
                uh, ur, rm = self._upsert_enriched_tournament(
                    local_tournament=t,
                    event=event_details or matched_event,
                    tournament=chosen,
                    players=players,
                    bracket_rows=brackets,
                    tab_matches=tab_matches,
                )
                stats.updated_history_rows += uh
                stats.upserted_results += ur
                stats.replaced_matches += rm
                logger.info(
                    "Enriched %s -> event=%s tournament=%s players=%s matches=%s",
                    t["tournament_id"],
                    (event_details.get("slug") or matched_event.get("slug")),
                    chosen.get("slug"),
                    len(players),
                    len(brackets),
                )
            except Exception as exc:  # noqa: BLE001
                stats.errors += 1
                logger.warning("ExternalPool harvest failed for %s: %s", t.get("tournament_id"), exc)
        return stats.to_dict()

    def harvest_by_slug(
        self,
        slug: str,
        *,
        local_tournament_id: Optional[str] = None,
        update_database: bool = True,
        force: bool = False,
        skip_if_bracket_url_exists: bool = True,
    ) -> Dict[str, Any]:
        """
        Fetch one ExternalPool tournament by public URL slug (no fuzzy event search).

        If ``local_tournament_id`` is set, loads that ``tournament_history`` row and can
        upsert URLs, results, and matches (same as batch ``harvest``).

        If omitted, writes an archive JSON only (prefix ``slug_<slug>``); no DB updates.
        ``update_database`` is forced False when no local tournament id is provided.
        """
        out: Dict[str, Any] = {
            "slug": (slug or "").strip(),
            "ok": False,
            "archive_path": None,
            "remote_tournament_id": None,
            "updated_history_rows": 0,
            "upserted_results": 0,
            "replaced_matches": 0,
            "skipped": None,
            "error": None,
        }
        slug_clean = (slug or "").strip()
        if not slug_clean:
            out["error"] = "empty_slug"
            return out

        chosen = self._fetch_tournament_by_slug(slug_clean)
        if not chosen:
            out["error"] = "tournament_not_found"
            return out
        tid = int(chosen["id"])
        out["remote_tournament_id"] = tid

        event_id = chosen.get("event_id")
        event: Dict[str, Any] = {}
        if event_id is not None:
            event = self._fetch_event_by_pk(int(event_id))

        local_tournament: Dict[str, Any]
        if local_tournament_id:
            row = self._load_local_tournament_row(local_tournament_id)
            if not row:
                out["error"] = "local_tournament_not_found"
                return out
            local_tournament = row
            if (
                not force
                and skip_if_bracket_url_exists
                and (row.get("bracket_url") or "").strip()
                and "digitalpool.com" in (row.get("bracket_url") or "").lower()
            ):
                out["skipped"] = "existing_bracket_url"
                out["ok"] = True
                return out
        else:
            update_database = False
            local_tournament = {
                "tournament_id": None,
                "name": chosen.get("name"),
                "date": None,
                "association": None,
                "bracket_url": None,
            }

        players = self._fetch_tournament_players(tid)
        brackets = self._fetch_tournament_brackets(tid)
        tab_matches = self._fetch_tournament_matches(tid)
        archive_path = self._persist_raw_tab_payload(
            local_tournament=local_tournament,
            event=event,
            tournament=chosen,
            players=players,
            bracket_rows=brackets,
            tab_matches=tab_matches,
            slug=slug_clean,
        )
        out["archive_path"] = str(archive_path)
        out["ok"] = True

        if update_database and local_tournament.get("tournament_id"):
            uh, ur, rm = self._upsert_enriched_tournament(
                local_tournament=local_tournament,
                event=event,
                tournament=chosen,
                players=players,
                bracket_rows=brackets,
                tab_matches=tab_matches,
            )
            out["updated_history_rows"] = uh
            out["upserted_results"] = ur
            out["replaced_matches"] = rm

        return out

