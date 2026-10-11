"""
Digital Pool event *discovery* enumerator (Phase 3 of
docs/MULTI_SOURCE_DATA_INTEGRATION_PLAN.md).

The existing ``ExternalPoolTournamentHarvester`` is **local-first**: it walks
existing ``tournament_history`` rows and enriches them from Digital Pool. This
module is the inverse — it **enumerates the Digital Pool catalog** (the public
``events`` table on the Hasura GraphQL API) to discover events we do *not* have
locally, de-duplicating each against ``tournament_history`` through the Phase-1
``EventCrosswalkResolver`` so nothing is double-counted.

Reality check (probed 2026-06-09): the public ``events`` table is ~1.7k rows
(865 public), NOT 92k — and most are small regional/local tournaments (e.g.
"Electric City 10 Ball", "Gateway 9 Ball Series"), not pro-tour events. Org-name
scoping is tiny (wpa=10, wpba=18, matchroom=0). So a firehose ingest would flood
the rankings DB with low-relevance data (docs §7). This enumerator therefore
**reports first**: it classifies DP-only events by pro-relevance and never
inserts ``tournament_history`` rows on its own — ingestion scope is an explicit
operator decision (a later, reviewed step).

Read-only on Digital Pool; the only writes are crosswalk rows for events that
already match a local tournament (idempotent). Manual/admin-triggered only.

Pagination: keyset on ``id`` descending (``events`` ids are monotonic) — avoids
large-offset degradation per Hasura/Postgres guidance.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from api.services.event_crosswalk import EventCrosswalkResolver, SOURCE_DIGITALPOOL
from scrapers.externalpool_tournament_harvester import (
    EXTERNALPOOL_BASE_URL,
    ExternalPoolTournamentHarvester,
)

logger = logging.getLogger(__name__)

# Distinctive pro / governing-body / major-tour tokens. Used only to *classify*
# DP-only events in the report (pro-like vs local), never to silently drop data.
# Kept conservative to avoid generic words ("open", "world") matching local events.
DEFAULT_PRO_KEYWORDS: List[str] = [
    "wpa", "wpba", "mosconi", "matchroom", "world championship",
    "world pool", "world cup", "world 9-ball", "world 10-ball",
    "us open 9", "us open 10", "predator world", "predator championship",
    "international 9-ball", "international 10-ball", "euro tour", "eurotour",
    "china open", "uk open", "world masters", "reyes", "hanoi",
]

_DEFAULT_DATE_FLOOR = "2023-01-01"
_DEFAULT_PAGE_SIZE = 100


@dataclass
class EnumerationReport:
    scanned: int = 0
    matched_existing: int = 0
    crosswalk_recorded: int = 0
    dp_only: int = 0
    dp_only_pro_like: int = 0
    dp_only_with_placements: int = 0
    pages: int = 0
    errors: int = 0
    by_year: Counter = field(default_factory=Counter)
    pro_like_samples: List[Dict[str, Any]] = field(default_factory=list)
    archive_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scanned": self.scanned,
            "matched_existing": self.matched_existing,
            "crosswalk_recorded": self.crosswalk_recorded,
            "dp_only": self.dp_only,
            "dp_only_pro_like": self.dp_only_pro_like,
            "dp_only_with_placements": self.dp_only_with_placements,
            "pages": self.pages,
            "errors": self.errors,
            "dp_only_by_year": dict(sorted(self.by_year.items())),
            "pro_like_samples": self.pro_like_samples[:25],
            "archive_path": self.archive_path,
        }


class ExternalPoolEventEnumerator:
    def __init__(
        self,
        *,
        harvester: Optional[ExternalPoolTournamentHarvester] = None,
        resolver: Optional[EventCrosswalkResolver] = None,
        pro_keywords: Optional[List[str]] = None,
    ) -> None:
        # Reuse the harvester purely for its polite GraphQL plumbing (_graphql/_pace).
        self.harvester = harvester or ExternalPoolTournamentHarvester()
        self.resolver = resolver or EventCrosswalkResolver(db=self.harvester.db)
        self.pro_keywords = [k.lower() for k in (pro_keywords or DEFAULT_PRO_KEYWORDS)]
        self.archive_dir = Path(
            os.getenv("EXTERNALPOOL_ENUM_ARCHIVE_DIR", "scraped_data/externalpool_enum")
        )
        self._archive_enabled = True
        try:
            self.archive_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning("DP enumerator: archive dir unavailable (%s); archiving disabled", e)
            self._archive_enabled = False

    def _is_pro_like(self, name: str) -> bool:
        n = (name or "").lower()
        return any(kw in n for kw in self.pro_keywords)

    def _fetch_page(self, *, date_floor: str, public_only: bool,
                    cursor_id: Optional[int], page_size: int) -> List[Dict[str, Any]]:
        conds = ['{ deleted_at: { _is_null: true } }']
        if public_only:
            conds.append('{ is_public: { _eq: true } }')
        conds.append('{ start_date_time: { _gte: $dateFloor } }')
        if cursor_id is not None:
            conds.append('{ id: { _lt: $cursorId } }')
        where = "{ _and: [ " + " ".join(conds) + " ] }"
        # $cursorId is declared but only referenced when cursor_id is set; Hasura
        # tolerates unused declared vars, so we keep one query shape.
        query = f"""
        query EnumEvents($dateFloor: timestamptz!, $cursorId: Int, $limit: Int!) {{
          events(
            where: {where}
            order_by: [{{ id: desc }}]
            limit: $limit
          ) {{
            id
            name
            slug
            start_date_time
            end_date_time
            location
            tournaments_aggregate {{ aggregate {{ count }} }}
            tournaments(limit: 1, order_by: [{{ id: asc }}]) {{
              status
              tournament_players_aggregate {{ aggregate {{ count }} }}
            }}
          }}
        }}
        """
        variables: Dict[str, Any] = {
            "dateFloor": f"{date_floor}T00:00:00+00:00",
            "limit": int(page_size),
        }
        if cursor_id is not None:
            variables["cursorId"] = int(cursor_id)
        data = self.harvester._graphql(query, variables)
        return data.get("events") or []

    @staticmethod
    def _placement_count(event: Dict[str, Any]) -> int:
        t = event.get("tournaments") or []
        if not t:
            return 0
        agg = (t[0].get("tournament_players_aggregate") or {}).get("aggregate") or {}
        return int(agg.get("count") or 0)

    def enumerate(
        self,
        *,
        date_floor: Optional[str] = None,
        public_only: bool = True,
        page_size: int = _DEFAULT_PAGE_SIZE,
        max_events: Optional[int] = None,
        record_crosswalk: bool = True,
    ) -> Dict[str, Any]:
        """Walk the DP catalog and report the local-vs-DP-only breakdown.

        - ``date_floor``: ISO date; only events on/after are scanned (default 2023-01-01).
        - ``public_only``: restrict to ``is_public`` events (default True).
        - ``record_crosswalk``: when an event matches an existing tournament, persist
          the crosswalk row (idempotent). Never creates ``tournament_history`` rows.
        """
        date_floor = date_floor or os.getenv("EXTERNALPOOL_ENUM_DATE_FLOOR", _DEFAULT_DATE_FLOOR)
        report = EnumerationReport()
        self.resolver.ensure_table()

        dp_only_records: List[Dict[str, Any]] = []
        cursor_id: Optional[int] = None

        while True:
            try:
                page = self._fetch_page(
                    date_floor=date_floor, public_only=public_only,
                    cursor_id=cursor_id, page_size=page_size,
                )
            except Exception as exc:  # noqa: BLE001
                report.errors += 1
                logger.warning("DP enumerate page failed (cursor=%s): %s", cursor_id, exc)
                break
            if not page:
                break
            report.pages += 1

            for ev in page:
                report.scanned += 1
                cursor_id = int(ev["id"]) if ev.get("id") is not None else cursor_id
                name = ev.get("name") or ""
                slug = ev.get("slug")
                start = ev.get("start_date_time")
                year = str(start)[:4] if start else "unknown"

                try:
                    res = self.resolver.resolve(
                        source=SOURCE_DIGITALPOOL,
                        source_event_id=slug or str(ev.get("id")),
                        name=name,
                        event_date=start,
                        location=ev.get("location"),
                        source_url=f"{EXTERNALPOOL_BASE_URL}/events/{slug}" if slug else None,
                        use_llm=False,  # bulk pass: keep it deterministic + fast
                    )
                except Exception as exc:  # noqa: BLE001
                    report.errors += 1
                    logger.debug("crosswalk resolve failed for DP event %s: %s", ev.get("id"), exc)
                    continue

                if res.matched:
                    report.matched_existing += 1
                    if record_crosswalk and res.match_method != "crosswalk":
                        report.crosswalk_recorded += 1
                    continue

                # DP-only event (not in tournament_history).
                report.dp_only += 1
                report.by_year[year] += 1
                placements = self._placement_count(ev)
                pro_like = self._is_pro_like(name)
                if placements > 0:
                    report.dp_only_with_placements += 1
                if pro_like:
                    report.dp_only_pro_like += 1
                rec = {
                    "dp_event_id": ev.get("id"),
                    "slug": slug,
                    "name": name,
                    "start_date": start,
                    "end_date": ev.get("end_date_time"),
                    "location": ev.get("location"),
                    "tournament_count": (ev.get("tournaments_aggregate") or {})
                        .get("aggregate", {}).get("count"),
                    "placement_count": placements,
                    "pro_like": pro_like,
                    "url": f"{EXTERNALPOOL_BASE_URL}/events/{slug}" if slug else None,
                }
                dp_only_records.append(rec)
                if pro_like and len(report.pro_like_samples) < 25:
                    report.pro_like_samples.append(rec)

                if max_events and report.scanned >= max_events:
                    break

            if len(page) < page_size:
                break
            if max_events and report.scanned >= max_events:
                break

        report.archive_path = self._archive(dp_only_records, date_floor)
        logger.info("DP enumeration report: %s", report.to_dict())
        return report.to_dict()

    # ---- Phase 3b: ingest selected DP-only events --------------------------

    @staticmethod
    def _classify_association(name: str) -> str:
        """Best-effort governing-body label for an ingested DP event. Free-form on
        tournament_history (no CHECK); the UI renders any value under 'All'."""
        n = (name or "").lower()
        if "wpba" in n:
            return "WPBA"
        if "nwpa" in n:  # regional, not WPA — checked before the 'wpa' substring
            return "DigitalPool"
        if "wpa" in n:
            return "WPA"
        return "DigitalPool"

    @staticmethod
    def _event_date(name: str, start_date_time: Any) -> Optional[date]:
        """Parse the DP start date, clamping an obviously-wrong year to the
        4-digit year in the event name when they disagree (DP has some bad dates,
        e.g. 'World Pool Championship 2022' dated 2026)."""
        if not start_date_time:
            return None
        try:
            d = datetime.fromisoformat(str(start_date_time).replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            return None
        m = re.search(r"\b(19|20)\d{2}\b", name or "")
        if m:
            name_year = int(m.group(0))
            if abs(name_year - d.year) >= 2:
                try:
                    return d.replace(year=name_year)
                except ValueError:
                    return date(name_year, d.month if d.month != 29 else 28, 1)
        return d

    def _choose_tournament(self, tournaments: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not tournaments:
            return None
        ranked = sorted(
            tournaments,
            key=lambda x: (
                0 if str(x.get("status") or "").upper() == "COMPLETED" else 1,
                -(x.get("tournament_brackets_aggregate", {}).get("aggregate", {}).get("count") or 0),
                -(x.get("tournament_players_aggregate", {}).get("aggregate", {}).get("count") or 0),
            ),
        )
        return ranked[0]

    def _insert_tournament_history(self, *, tournament_id: str, name: str,
                                   event_date: Optional[date], location: Optional[str],
                                   association: str, source_url: Optional[str],
                                   bracket_url: Optional[str]) -> bool:
        """Idempotent INSERT of a discovered DP event. Returns True if a new row was created."""
        with self.harvester.db.engine.begin() as conn:
            res = conn.execute(
                text("""
                    INSERT INTO tournament_history
                        (tournament_id, name, date, year, location, association, status,
                         source_url, bracket_url, created_at, updated_at)
                    VALUES
                        (:tid, :name, :date, :year, :location, :assoc, 'completed',
                         :source_url, :bracket_url, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (tournament_id) DO NOTHING
                """),
                {
                    "tid": tournament_id,
                    "name": name[:255],
                    "date": event_date,
                    "year": event_date.year if event_date else None,
                    "location": (location or None),
                    "assoc": association,
                    "source_url": source_url,
                    "bracket_url": bracket_url,
                },
            )
            return int(res.rowcount or 0) > 0

    def ingest(
        self,
        *,
        date_floor: Optional[str] = None,
        public_only: bool = True,
        page_size: int = _DEFAULT_PAGE_SIZE,
        only_pro: bool = True,
        require_placements: bool = True,
        max_ingest: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Ingest DP-only events matching the scope into tournament_history and enrich
        them (results + bracket/match rows + tab archive) via the local-first harvester.

        Default scope = pro-like events with placements (the operator-approved set).
        Idempotent: existing crosswalk / tournament rows are skipped.
        """
        date_floor = date_floor or os.getenv("EXTERNALPOOL_ENUM_DATE_FLOOR", _DEFAULT_DATE_FLOOR)
        self.resolver.ensure_table()
        stats = {
            "scanned": 0, "selected": 0, "inserted": 0, "enriched": 0,
            "skipped_existing": 0, "skipped_no_tournament": 0, "errors": 0,
            "results_upserted": 0, "matches_upserted": 0,
            "ingested": [],
        }
        cursor_id: Optional[int] = None

        while True:
            try:
                page = self._fetch_page(date_floor=date_floor, public_only=public_only,
                                        cursor_id=cursor_id, page_size=page_size)
            except Exception as exc:  # noqa: BLE001
                stats["errors"] += 1
                logger.warning("DP ingest page failed (cursor=%s): %s", cursor_id, exc)
                break
            if not page:
                break

            for ev in page:
                stats["scanned"] += 1
                cursor_id = int(ev["id"]) if ev.get("id") is not None else cursor_id
                name = ev.get("name") or ""
                if only_pro and not self._is_pro_like(name):
                    continue
                if require_placements and self._placement_count(ev) <= 0:
                    continue
                stats["selected"] += 1
                try:
                    self._ingest_one(ev, stats)
                except Exception as exc:  # noqa: BLE001
                    stats["errors"] += 1
                    logger.warning("DP ingest failed for event %s (%s): %s",
                                   ev.get("id"), name[:60], exc)
                if max_ingest and stats["inserted"] >= max_ingest:
                    break

            if len(page) < page_size:
                break
            if max_ingest and stats["inserted"] >= max_ingest:
                break

        logger.info("DP ingest stats: %s", {k: v for k, v in stats.items() if k != "ingested"})
        return stats

    def _ingest_one(self, ev: Dict[str, Any], stats: Dict[str, Any]) -> None:
        name = ev.get("name") or ""
        slug = ev.get("slug")
        event_id = ev.get("id")
        start = ev.get("start_date_time")

        # 1) Already linked / matches an existing local tournament -> skip (idempotent).
        existing = self.resolver.resolve(
            source=SOURCE_DIGITALPOOL,
            source_event_id=slug or str(event_id),
            name=name, event_date=start, location=ev.get("location"),
            source_url=f"{EXTERNALPOOL_BASE_URL}/events/{slug}" if slug else None,
            use_llm=False,
        )
        if existing.matched:
            stats["skipped_existing"] += 1
            return

        # 2) Pull the event's tournaments and pick the richest completed one.
        details = self.harvester._fetch_event_tournaments(int(event_id))
        chosen = self._choose_tournament(details.get("tournaments") or [])
        if not chosen:
            stats["skipped_no_tournament"] += 1
            return

        tid_remote = int(chosen["id"])
        tournament_id = f"dp_{slug}" if slug else f"dp_evt_{event_id}"
        association = self._classify_association(name)
        ev_date = self._event_date(name, start)
        event_url = f"{EXTERNALPOOL_BASE_URL}/events/{slug}" if slug else None
        bracket_url = (
            f"{EXTERNALPOOL_BASE_URL}/tournaments/{chosen.get('slug')}/viewer"
            if chosen.get("slug") else None
        )

        created = self._insert_tournament_history(
            tournament_id=tournament_id, name=name, event_date=ev_date,
            location=ev.get("location"), association=association,
            source_url=event_url, bracket_url=bracket_url,
        )
        if created:
            stats["inserted"] += 1

        # 3) Enrich placements + bracket/match rows + tab archive (reuse harvester).
        local_tournament = {
            "tournament_id": tournament_id, "name": name,
            "date": ev_date, "association": association, "bracket_url": bracket_url,
        }
        players = self.harvester._fetch_tournament_players(tid_remote)
        brackets = self.harvester._fetch_tournament_brackets(tid_remote)
        tab_matches = self.harvester._fetch_tournament_matches(tid_remote)
        try:
            self.harvester._persist_raw_tab_payload(
                local_tournament=local_tournament,
                event=details or ev, tournament=chosen,
                players=players, bracket_rows=brackets, tab_matches=tab_matches,
                slug=slug,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("tab archive persist failed for %s: %s", tournament_id, exc)
        uh, ur, rm = self.harvester._upsert_enriched_tournament(
            local_tournament=local_tournament,
            event=details or ev, tournament=chosen,
            players=players, bracket_rows=brackets, tab_matches=tab_matches,
        )
        stats["enriched"] += 1
        stats["results_upserted"] += ur
        stats["matches_upserted"] += rm

        # 4) Record the crosswalk so re-runs are idempotent and future scrapes link here.
        self.resolver.record(
            tournament_id=tournament_id, source=SOURCE_DIGITALPOOL,
            source_event_id=slug or str(event_id), source_url=event_url,
            match_method="ingest",
        )
        stats["ingested"].append({
            "tournament_id": tournament_id, "name": name,
            "date": str(ev_date) if ev_date else None,
            "association": association, "players": len(players),
            "results_upserted": ur, "matches_upserted": rm,
        })
        logger.info("Ingested DP event -> %s (%s, %s players, %s results)",
                    tournament_id, association, len(players), ur)

    def _archive(self, dp_only: List[Dict[str, Any]], date_floor: str) -> Optional[str]:
        if not self._archive_enabled or not dp_only:
            return None
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        payload = {
            "metadata": {
                "captured_at": datetime.utcnow().isoformat() + "Z",
                "source": "digitalpool_events_enumeration",
                "date_floor": date_floor,
                "dp_only_count": len(dp_only),
            },
            "dp_only_events": dp_only,
        }
        path = self.archive_dir / f"dp_only_events_{ts}.json"
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                            encoding="utf-8")
            logger.info("DP enumerator: archived %s DP-only events to %s", len(dp_only), path)
            return str(path)
        except OSError as e:
            logger.error("DP enumerator: archive failed: %s", e)
            return None


def enumerate_digitalpool_events(**kwargs) -> Dict[str, Any]:
    """Convenience entry point (CLI / admin)."""
    return ExternalPoolEventEnumerator().enumerate(**kwargs)
