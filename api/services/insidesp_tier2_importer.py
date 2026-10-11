"""Inside Spin Tier-2 importer — historical events + gap-fill results.

Phase 4 of docs/MULTI_SOURCE_DATA_INTEGRATION_PLAN.md. Uses the Tier-2 scraper
(API catalog + RSC participantRows) and the Phase-1 ``EventCrosswalkResolver``
so we never double-count events that Digital Pool (or local SSOT) already owns.

Default scope (conservative, operator-approved pattern from DP Phase 3b):
- ``only_pro=True``: major-tour / governing-body keywords only
- ``require_results=True``: skip events with ``results_count == 0``
- For **crosswalk-matched** events: gap-fill ``tournament_results`` only when the
  local row has zero results (never clobber DP/WPBA/WPA results).
- For **IS-only** events (no crosswalk match): INSERT ``tournament_history`` as
  ``insidesp_{slug}`` and write results.

Manual / admin-triggered only.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from api.services.event_crosswalk import EventCrosswalkResolver, SOURCE_INSIDESP
from database import get_database_manager
from scrapers.insidesp_tier2_scraper import InsideSpinTier2Scraper

logger = logging.getLogger(__name__)

DEFAULT_BEGIN_YEAR = 2020


class InsideSpinTier2Importer:
    def __init__(
        self,
        scraper: Optional[InsideSpinTier2Scraper] = None,
        resolver: Optional[EventCrosswalkResolver] = None,
        db: Any = None,
    ) -> None:
        self.scraper = scraper or InsideSpinTier2Scraper()
        self.db = db or get_database_manager()
        self.resolver = resolver or EventCrosswalkResolver(db=self.db)

    @staticmethod
    def _as_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _extract_year(name: str, event_date: Optional[date]) -> int:
        m = re.search(r"\b(19|20)\d{2}\b", name or "")
        if m:
            return int(m.group(0))
        if event_date:
            return event_date.year
        return datetime.utcnow().year

    @staticmethod
    def _classify_association(name: str, tour_name: Optional[str] = None) -> str:
        blob = f"{name or ''} {tour_name or ''}".lower()
        if "wpba" in blob:
            return "WPBA"
        if "wpa" in blob and "nwpa" not in blob:
            return "WPA"
        return "Inside Spin"

    def _local_results_count(self, tournament_id: str) -> int:
        with self.db.engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) FROM tournament_results WHERE tournament_id = :tid"),
                {"tid": tournament_id},
            ).fetchone()
            return int(row[0] or 0) if row else 0

    def _upsert_tournament_history(
        self,
        conn,
        *,
        tournament_id: str,
        name: str,
        event_date: Optional[date],
        association: str,
        source_url: str,
        location: Optional[str] = None,
    ) -> bool:
        """Insert tournament_history if missing. Returns True when a new row was created."""
        year = self._extract_year(name, event_date)
        insert_date = event_date or date(year, 1, 1)
        res = conn.execute(
            text("""
                INSERT INTO tournament_history
                (tournament_id, name, year, date, association, status, source_url, location)
                VALUES (:tid, :name, :year, CAST(:dt AS date), :assoc, 'completed', :url, :loc)
                ON CONFLICT (tournament_id) DO NOTHING
            """),
            {
                "tid": tournament_id,
                "name": name[:255],
                "year": year,
                "dt": str(insert_date),
                "assoc": association[:64],
                "url": source_url,
                "loc": (location or "")[:255] or None,
            },
        )
        return (res.rowcount or 0) > 0

    def _write_results(
        self,
        conn,
        *,
        tournament_id: str,
        result_rows: List[Dict[str, Any]],
        replace: bool,
    ) -> int:
        if replace:
            conn.execute(
                text("DELETE FROM tournament_results WHERE tournament_id = :tid"),
                {"tid": tournament_id},
            )
        n = 0
        for row in result_rows:
            name = (row.get("player_name") or "").strip()
            if not name:
                continue
            placement = row.get("placement")
            if placement is None:
                continue
            conn.execute(
                text("""
                    INSERT INTO tournament_results
                    (tournament_id, player_name, placement, points, stops_played)
                    VALUES (:tid, :player, :placement, :points, NULL)
                    ON CONFLICT (tournament_id, player_name) DO UPDATE SET
                        placement = EXCLUDED.placement,
                        points = EXCLUDED.points
                """),
                {
                    "tid": tournament_id,
                    "player": name[:255],
                    "placement": int(placement),
                    "points": float(row.get("points") or 0),
                },
            )
            n += 1
        return n

    def ingest(
        self,
        *,
        begin_year: int = DEFAULT_BEGIN_YEAR,
        end_year: Optional[int] = None,
        only_pro: bool = True,
        require_results: bool = True,
        max_events: Optional[int] = None,
        fetch_detail: bool = True,
        gap_fill_only: bool = False,
    ) -> Dict[str, Any]:
        """Run Tier-2 ingestion for the year range."""
        end_year = end_year or datetime.utcnow().year
        self.resolver.ensure_table()

        catalog = self.scraper.fetch_tournaments_catalog(begin_year, end_year)
        archive = self.scraper.archive_catalog(catalog, f"{begin_year}_{end_year}")

        stats: Dict[str, Any] = {
            "begin_year": begin_year,
            "end_year": end_year,
            "catalog_count": len(catalog),
            "archive_path": archive,
            "scanned": 0,
            "skipped_not_pro": 0,
            "skipped_no_results": 0,
            "matched_existing": 0,
            "gap_filled": 0,
            "inserted_history": 0,
            "results_written": 0,
            "skipped_has_results": 0,
            "errors": 0,
            "ingested": [],
        }

        processed = 0
        for ev in catalog:
            if max_events is not None and processed >= max_events:
                break
            stats["scanned"] += 1
            name = (ev.get("name") or "").strip()
            slug = (ev.get("name_slug") or "").strip()
            if not name or not slug:
                continue

            if only_pro and not self.scraper.is_pro_like(name):
                stats["skipped_not_pro"] += 1
                continue

            results_count = int(ev.get("results_count") or 0)
            if require_results and results_count <= 0:
                stats["skipped_no_results"] += 1
                continue

            start_date = self._as_date(ev.get("start_date"))
            source_url = f"{InsideSpinTier2Scraper.BASE_URL}/tournaments/{slug}"

            try:
                resolution = self.resolver.resolve(
                    source=SOURCE_INSIDESP,
                    source_event_id=slug,
                    name=name,
                    event_date=start_date,
                    location=ev.get("location"),
                    source_url=source_url,
                    use_llm=False,
                )
            except Exception as exc:  # noqa: BLE001
                stats["errors"] += 1
                logger.warning("Inside Spin Tier-2 crosswalk failed for %s: %s", slug, exc)
                continue

            result_rows: List[Dict[str, Any]] = []
            if fetch_detail:
                try:
                    participant_rows = self.scraper.fetch_participant_rows(slug)
                    result_rows = self.scraper.rows_to_results(
                        participant_rows,
                        top_finishers=ev.get("top_finishers"),
                    )
                except Exception as exc:  # noqa: BLE001
                    stats["errors"] += 1
                    logger.warning("Inside Spin Tier-2 detail fetch failed for %s: %s", slug, exc)
                    result_rows = self.scraper.rows_to_results([], top_finishers=ev.get("top_finishers"))
            else:
                result_rows = self.scraper.rows_to_results([], top_finishers=ev.get("top_finishers"))

            if not result_rows:
                stats["skipped_no_results"] += 1
                continue

            if gap_fill_only and not resolution.matched:
                processed += 1
                continue

            try:
                tid: Optional[str] = None
                mode: Optional[str] = None
                n = 0
                existing_n = 0
                if resolution.matched and resolution.tournament_id:
                    existing_n = self._local_results_count(resolution.tournament_id)
                with self.db.engine.begin() as conn:
                    if resolution.matched and resolution.tournament_id:
                        stats["matched_existing"] += 1
                        tid = resolution.tournament_id
                        if existing_n > 0:
                            stats["skipped_has_results"] += 1
                            processed += 1
                            continue
                        n = self._write_results(conn, tournament_id=tid, result_rows=result_rows, replace=False)
                        stats["gap_filled"] += 1
                        mode = "gap_fill"
                    elif gap_fill_only:
                        processed += 1
                        continue
                    else:
                        tid = f"insidesp_{slug}"
                        assoc = self._classify_association(name, ev.get("tour_name"))
                        created = self._upsert_tournament_history(
                            conn,
                            tournament_id=tid,
                            name=name,
                            event_date=start_date,
                            association=assoc,
                            source_url=source_url,
                            location=ev.get("location"),
                        )
                        if created:
                            stats["inserted_history"] += 1
                        n = self._write_results(conn, tournament_id=tid, result_rows=result_rows, replace=True)
                        mode = "insert"

                if tid and mode:
                    # Record crosswalk after tournament_history commit (FK-safe).
                    self.resolver.record(
                        tournament_id=tid,
                        source=SOURCE_INSIDESP,
                        source_event_id=slug,
                        source_url=source_url,
                        match_method="ingest",
                    )
                    stats["results_written"] += n
                    stats["ingested"].append({
                        "tournament_id": tid,
                        "name": name,
                        "slug": slug,
                        "mode": mode,
                        "results": n,
                    })
            except Exception as exc:  # noqa: BLE001
                stats["errors"] += 1
                logger.warning("Inside Spin Tier-2 DB write failed for %s: %s", slug, exc)

            processed += 1

        logger.info("Inside Spin Tier-2 ingest stats: %s", {k: v for k, v in stats.items() if k != "ingested"})
        return stats

    def report(
        self,
        *,
        begin_year: int = DEFAULT_BEGIN_YEAR,
        end_year: Optional[int] = None,
        only_pro: bool = True,
    ) -> Dict[str, Any]:
        """Read-only catalog + crosswalk breakdown (no DB writes except crosswalk on match)."""
        end_year = end_year or datetime.utcnow().year
        self.resolver.ensure_table()
        catalog = self.scraper.fetch_tournaments_catalog(begin_year, end_year)
        archive = self.scraper.archive_catalog(catalog, f"report_{begin_year}_{end_year}")

        matched = is_only = pro_like = with_results = 0
        for ev in catalog:
            name = ev.get("name") or ""
            slug = ev.get("name_slug") or ""
            if only_pro and not self.scraper.is_pro_like(name):
                continue
            pro_like += 1
            if int(ev.get("results_count") or 0) <= 0:
                continue
            with_results += 1
            res = self.resolver.resolve(
                source=SOURCE_INSIDESP,
                source_event_id=slug,
                name=name,
                event_date=self._as_date(ev.get("start_date")),
                location=ev.get("location"),
                source_url=f"{InsideSpinTier2Scraper.BASE_URL}/tournaments/{slug}",
                use_llm=False,
            )
            if res.matched:
                matched += 1
            else:
                is_only += 1

        return {
            "begin_year": begin_year,
            "end_year": end_year,
            "catalog_count": len(catalog),
            "pro_like_with_results": with_results,
            "matched_existing": matched,
            "is_only_with_results": is_only,
            "archive_path": archive,
        }
