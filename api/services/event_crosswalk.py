"""Cross-source event crosswalk + merge helper.

Keeps one ``tournament_history.tournament_id`` per real event across multiple
external sources (digitalpool.com, insidesp.in, ...). See
``docs/MULTI_SOURCE_DATA_INTEGRATION_PLAN.md`` §3a and Alembic ``055``.

De-dup decision (date-first, name + location):
- candidate events must fall within a date window of the incoming event
  (``CROSSWALK_CANDIDATE_WINDOW_DAYS``, default 5), then
- name similarity reuses the **same** normalization/blend as the tournament
  harvester (``ExternalPoolTournamentHarvester._norm_name`` / ``_token_jaccard``)
  so we have a single normalization SSOT, plus a small location bonus.
- a confident score (>= ``CROSSWALK_MATCH_MIN_SCORE``, default 0.55) with a date
  match => same event (merge). The gray zone is arbitrated by
  ``ollama_name_resolver`` (already used by the harvester). Below that => distinct
  events (no silent merge — caller creates a new tournament_history row).

This module never fuzzy-merges on its own beyond these guards, consistent with
the no-workarounds / identity policy in ``docs/WPA_TOURNAMENT_SSOT.md`` §5a.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from database import get_database_manager
from scrapers.externalpool_tournament_harvester import ExternalPoolTournamentHarvester

logger = logging.getLogger(__name__)

# Sources we recognize. Free-form VARCHAR in DB, but keep canonical labels here.
SOURCE_DIGITALPOOL = "digitalpool"
SOURCE_INSIDESP = "insidesp"

_DEFAULT_MIN_SCORE = 0.55
_DEFAULT_CANDIDATE_WINDOW_DAYS = 5
_DEFAULT_DATE_MATCH_DAYS = 2

# Slug extractors for existing digitalpool URLs already stored on tournament_history.
_DP_SLUG_RES = (
    re.compile(r"digitalpool\.com/tournaments/([^/?#]+)", re.I),
    re.compile(r"digitalpool\.com/events/([^/?#]+)", re.I),
)


@dataclass
class CrosswalkResolution:
    """Result of resolving an incoming source event against local tournaments."""
    tournament_id: Optional[str]
    matched: bool
    match_method: Optional[str] = None
    match_score: Optional[float] = None
    candidate_count: int = 0


class EventCrosswalkResolver:
    def __init__(
        self,
        db: Any = None,
        *,
        match_min_score: Optional[float] = None,
        candidate_window_days: Optional[int] = None,
        date_match_days: Optional[int] = None,
    ) -> None:
        self.db = db or get_database_manager()
        self.min_score = float(
            match_min_score
            if match_min_score is not None
            else os.getenv("CROSSWALK_MATCH_MIN_SCORE", str(_DEFAULT_MIN_SCORE))
        )
        self.candidate_window_days = int(
            candidate_window_days
            if candidate_window_days is not None
            else os.getenv("CROSSWALK_CANDIDATE_WINDOW_DAYS", str(_DEFAULT_CANDIDATE_WINDOW_DAYS))
        )
        self.date_match_days = int(
            date_match_days
            if date_match_days is not None
            else os.getenv("CROSSWALK_DATE_MATCH_DAYS", str(_DEFAULT_DATE_MATCH_DAYS))
        )

    # ---- schema (defensive; migration 055 is the source of truth) ----------

    def ensure_table(self) -> None:
        with self.db.engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS source_event_crosswalk (
                    id              SERIAL PRIMARY KEY,
                    tournament_id   VARCHAR(255) NOT NULL
                                        REFERENCES tournament_history(tournament_id) ON DELETE CASCADE,
                    source          VARCHAR(32)  NOT NULL,
                    source_event_id VARCHAR(255) NOT NULL,
                    source_url      TEXT,
                    match_method    VARCHAR(32),
                    match_score     DOUBLE PRECISION,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_source_event UNIQUE (source, source_event_id)
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_source_event_crosswalk_tid "
                "ON source_event_crosswalk (tournament_id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_source_event_crosswalk_source "
                "ON source_event_crosswalk (source)"
            ))

    # ---- normalization / scoring (reuse harvester SSOT) --------------------

    @staticmethod
    def _norm(name: str) -> str:
        return ExternalPoolTournamentHarvester._norm_name(name or "")

    @staticmethod
    def _norm_location(loc: Optional[str]) -> str:
        v = (loc or "").lower()
        v = re.sub(r"[^a-z0-9]+", " ", v)
        return re.sub(r"\s+", " ", v).strip()

    def _name_score(self, name_a: str, name_b: str) -> float:
        n_a, n_b = self._norm(name_a), self._norm(name_b)
        if not n_a or not n_b:
            return 0.0
        ratio = SequenceMatcher(None, n_a, n_b).ratio()
        jacc = ExternalPoolTournamentHarvester._token_jaccard(n_a, n_b)
        # Same blend the harvester uses for event name scoring.
        return min(1.0, 0.72 * ratio + 0.28 * jacc)

    def _location_bonus(self, loc_a: Optional[str], loc_b: Optional[str]) -> float:
        a, b = self._norm_location(loc_a), self._norm_location(loc_b)
        if not a or not b:
            return 0.0
        ta, tb = set(a.split()), set(b.split())
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)

    def _combined_score(
        self,
        name_a: str,
        name_b: str,
        loc_a: Optional[str],
        loc_b: Optional[str],
    ) -> float:
        name_score = self._name_score(name_a, name_b)
        loc_bonus = self._location_bonus(loc_a, loc_b)
        # Location only nudges; name dominates. Capped at 1.0.
        return min(1.0, name_score + 0.10 * loc_bonus)

    @staticmethod
    def _as_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        s = str(value).strip()
        if not s:
            return None
        s = s.replace("Z", "+00:00")
        for parser in (
            lambda x: datetime.fromisoformat(x),
            lambda x: datetime.strptime(x[:10], "%Y-%m-%d"),
        ):
            try:
                return parser(s).date()
            except (ValueError, TypeError):
                continue
        return None

    # ---- crosswalk read/write ---------------------------------------------

    def get_crosswalk_tournament_id(self, source: str, source_event_id: str) -> Optional[str]:
        if not source or not source_event_id:
            return None
        with self.db.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT tournament_id FROM source_event_crosswalk "
                    "WHERE source = :source AND source_event_id = :sid LIMIT 1"
                ),
                {"source": source, "sid": source_event_id},
            ).first()
        return row[0] if row else None

    def _tournament_already_mapped_from_source(
        self, source: str, tournament_id: str, source_event_id: str
    ) -> bool:
        """True when this tournament already maps to a *different* event id of the same source.

        Crosswalk is 1:1 per source: two distinct source event ids (e.g. Championship
        League "Group 2" vs "Group 5") must never share one local tournament. Without
        this guard, fuzzy date+name matching merges sibling events ingested from the
        same source and silently drops their results.
        """
        with self.db.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM source_event_crosswalk "
                    "WHERE source = :source AND tournament_id = :tid "
                    "AND source_event_id != :sid LIMIT 1"
                ),
                {"source": source, "tid": tournament_id, "sid": source_event_id},
            ).first()
        return row is not None

    def record(
        self,
        *,
        tournament_id: str,
        source: str,
        source_event_id: str,
        source_url: Optional[str] = None,
        match_method: Optional[str] = None,
        match_score: Optional[float] = None,
    ) -> None:
        with self.db.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO source_event_crosswalk
                        (tournament_id, source, source_event_id, source_url, match_method, match_score)
                    VALUES (:tid, :source, :sid, :url, :method, :score)
                    ON CONFLICT (source, source_event_id) DO UPDATE SET
                        tournament_id = EXCLUDED.tournament_id,
                        source_url    = COALESCE(EXCLUDED.source_url, source_event_crosswalk.source_url),
                        match_method  = COALESCE(EXCLUDED.match_method, source_event_crosswalk.match_method),
                        match_score   = COALESCE(EXCLUDED.match_score, source_event_crosswalk.match_score),
                        updated_at    = CURRENT_TIMESTAMP
                    """
                ),
                {
                    "tid": tournament_id,
                    "source": source,
                    "sid": source_event_id,
                    "url": source_url,
                    "method": match_method,
                    "score": match_score,
                },
            )

    # ---- candidate search + resolution ------------------------------------

    def _candidate_tournaments(self, event_date: date) -> List[Dict[str, Any]]:
        lo = event_date - timedelta(days=self.candidate_window_days)
        hi = event_date + timedelta(days=self.candidate_window_days)
        with self.db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT tournament_id, name, date, location
                    FROM tournament_history
                    WHERE date IS NOT NULL AND date BETWEEN :lo AND :hi
                    """
                ),
                {"lo": lo, "hi": hi},
            ).mappings().all()
        return [dict(r) for r in rows]

    def find_matching_tournament(
        self,
        *,
        name: str,
        event_date: Optional[date],
        location: Optional[str] = None,
        use_llm: bool = True,
    ) -> Tuple[Optional[str], Optional[float], Optional[str], int]:
        """Return (tournament_id, score, method, candidate_count) or (None, ...)."""
        if not event_date:
            # Date is required for safe auto-merge (see plan §3a).
            return None, None, None, 0

        candidates = self._candidate_tournaments(event_date)
        if not candidates:
            return None, None, None, 0

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for c in candidates:
            c_date = self._as_date(c.get("date"))
            if c_date is None or abs((c_date - event_date).days) > self.date_match_days:
                continue
            score = self._combined_score(name, c.get("name") or "", location, c.get("location"))
            scored.append((score, c))

        if not scored:
            return None, None, None, len(candidates)

        scored.sort(key=lambda x: x[0], reverse=True)
        top_score, top = scored[0]

        if top_score >= self.min_score:
            return top["tournament_id"], top_score, "date+name", len(candidates)

        # Gray zone: LLM arbitration (same pattern as the harvester).
        if use_llm and top_score >= self.min_score * 0.7:
            if self._llm_confirms(name, top.get("name") or ""):
                logger.info(
                    "Crosswalk LLM-confirmed: '%s' <-> '%s' (score=%.3f)",
                    name, top.get("name"), top_score,
                )
                return top["tournament_id"], top_score, "llm", len(candidates)

        return None, None, None, len(candidates)

    @staticmethod
    def _llm_confirms(name_a: str, name_b: str) -> bool:
        try:
            import asyncio

            from api.services.ollama_name_resolver import resolve_name_match
        except ImportError:
            return False
        try:
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    resolve_name_match(
                        name_a,
                        name_b,
                        context={"kind": "tournament_event", "task": "cross_source_dedup"},
                    )
                )
            finally:
                loop.close()
            return bool(result and result.is_confident_match)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Crosswalk LLM arbitration failed: %s", exc)
            return False

    def resolve(
        self,
        *,
        source: str,
        source_event_id: str,
        name: str,
        event_date: Any = None,
        location: Optional[str] = None,
        source_url: Optional[str] = None,
        use_llm: bool = True,
    ) -> CrosswalkResolution:
        """Resolve an incoming source event to a local tournament_id (or none).

        1) existing crosswalk row -> that tournament (idempotent).
        2) date+name(+location) match to an existing tournament_history row ->
           record crosswalk and return it.
        3) otherwise no match (caller creates a new tournament, then calls
           ``record(...)`` with the new id).
        """
        existing = self.get_crosswalk_tournament_id(source, source_event_id)
        if existing:
            return CrosswalkResolution(tournament_id=existing, matched=True, match_method="crosswalk")

        d = self._as_date(event_date)
        tid, score, method, n = self.find_matching_tournament(
            name=name, event_date=d, location=location, use_llm=use_llm
        )
        if tid and self._tournament_already_mapped_from_source(source, tid, source_event_id):
            logger.info(
                "Crosswalk: rejecting fuzzy match %s -> %s (tournament already mapped "
                "from source=%s under a different event id)",
                source_event_id, tid, source,
            )
            return CrosswalkResolution(tournament_id=None, matched=False, candidate_count=n)
        if tid:
            self.record(
                tournament_id=tid,
                source=source,
                source_event_id=source_event_id,
                source_url=source_url,
                match_method=method,
                match_score=score,
            )
            return CrosswalkResolution(
                tournament_id=tid, matched=True, match_method=method,
                match_score=score, candidate_count=n,
            )
        return CrosswalkResolution(tournament_id=None, matched=False, candidate_count=n)

    # ---- backfill existing digitalpool rows --------------------------------

    @staticmethod
    def _extract_dp_slug(*urls: Optional[str]) -> Optional[str]:
        for url in urls:
            if not url:
                continue
            for rx in _DP_SLUG_RES:
                m = rx.search(url)
                if m:
                    slug = m.group(1).strip()
                    # strip trailing path segments like /viewer captured by greedy hosts
                    slug = slug.split("/")[0]
                    if slug and slug.lower() not in {"viewer", "bracket"}:
                        return slug
        return None

    def backfill_digitalpool(self, *, limit: Optional[int] = None) -> Dict[str, int]:
        """Seed crosswalk rows for tournament_history events already linked to
        digitalpool.com (via source_url / bracket_url). Idempotent."""
        self.ensure_table()
        query = """
            SELECT tournament_id, source_url, bracket_url
            FROM tournament_history
            WHERE (source_url ILIKE '%digitalpool.com%' OR bracket_url ILIKE '%digitalpool.com%')
            ORDER BY tournament_id
        """
        if limit:
            query += " LIMIT :limit"
        with self.db.engine.connect() as conn:
            rows = conn.execute(text(query), {"limit": int(limit)} if limit else {}).mappings().all()

        stats = {"scanned": 0, "recorded": 0, "skipped_no_slug": 0, "skipped_existing": 0}
        for r in rows:
            stats["scanned"] += 1
            slug = self._extract_dp_slug(r.get("bracket_url"), r.get("source_url"))
            if not slug:
                stats["skipped_no_slug"] += 1
                continue
            if self.get_crosswalk_tournament_id(SOURCE_DIGITALPOOL, slug):
                stats["skipped_existing"] += 1
                continue
            self.record(
                tournament_id=r["tournament_id"],
                source=SOURCE_DIGITALPOOL,
                source_event_id=slug,
                source_url=r.get("source_url") or r.get("bracket_url"),
                match_method="backfill",
            )
            stats["recorded"] += 1
        logger.info("Digital Pool crosswalk backfill: %s", stats)
        return stats


def backfill_digitalpool_crosswalk(limit: Optional[int] = None) -> Dict[str, int]:
    """Convenience entry point (CLI / admin route)."""
    return EventCrosswalkResolver().backfill_digitalpool(limit=limit)
