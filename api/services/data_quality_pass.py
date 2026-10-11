"""Data quality pass — Phase 5 of MULTI_SOURCE_DATA_INTEGRATION_PLAN.md.

Crosswalk summary, drift checks (Inside Spin API vs local counts), and alias
seeding hooks. Read-only except when ``apply_aliases=True``.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy import text

from database import get_database_manager

logger = logging.getLogger(__name__)

INSIDESP_API = "https://www.insidesp.in/api/tournaments"
INSIDESP_REFERER = "https://www.insidesp.in/tournaments"


class DataQualityPass:
    def __init__(self, db: Any = None) -> None:
        self.db = db or get_database_manager()

    def crosswalk_summary(self) -> Dict[str, Any]:
        with self.db.engine.connect() as conn:
            by_source = conn.execute(text("""
                SELECT source, COUNT(*) AS n
                FROM source_event_crosswalk
                GROUP BY source
                ORDER BY source
            """)).fetchall()
            total = conn.execute(text("SELECT COUNT(*) FROM source_event_crosswalk")).scalar()
            recent = conn.execute(text("""
                SELECT tournament_id, source, source_event_id, match_method, match_score, created_at
                FROM source_event_crosswalk
                ORDER BY created_at DESC NULLS LAST
                LIMIT 20
            """)).mappings().all()
        return {
            "total_rows": int(total or 0),
            "by_source": {r[0]: int(r[1]) for r in by_source},
            "recent": [dict(r) for r in recent],
        }

    def crosswalk_review_rows(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Fuzzy crosswalk matches pending operator review (date+name / llm), lowest score first."""
        with self.db.engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT c.id, c.tournament_id, c.source, c.source_event_id,
                       c.source_url, c.match_method, c.match_score, c.created_at,
                       t.name AS tournament_name, t.date AS tournament_date
                FROM source_event_crosswalk c
                LEFT JOIN tournament_history t ON t.tournament_id = c.tournament_id
                WHERE c.match_method IN ('date+name', 'llm')
                ORDER BY c.match_score ASC NULLS FIRST, c.id
                LIMIT :lim
            """), {"lim": limit}).mappings().all()
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d["created_at"] = str(d["created_at"]) if d.get("created_at") else None
            d["tournament_date"] = str(d["tournament_date"]) if d.get("tournament_date") else None
            out.append(d)
        return out

    def confirm_crosswalk_row(self, row_id: int) -> Dict[str, Any]:
        """Operator approves a fuzzy match; method becomes 'confirmed' (drops out of review).

        Refuses ('conflict') when another row of the same source already maps the same
        tournament under a different event id — confirming would lock in a 1:1 violation.
        """
        with self.db.engine.begin() as conn:
            row = conn.execute(text("""
                SELECT source, tournament_id, source_event_id FROM source_event_crosswalk
                WHERE id = :id AND match_method IN ('date+name', 'llm')
            """), {"id": row_id}).fetchone()
            if row is None:
                return {"ok": False, "reason": "not_found"}
            sibling = conn.execute(text("""
                SELECT 1 FROM source_event_crosswalk
                WHERE source = :source AND tournament_id = :tid
                  AND source_event_id != :sid LIMIT 1
            """), {"source": row[0], "tid": row[1], "sid": row[2]}).fetchone()
            if sibling is not None:
                return {"ok": False, "reason": "conflict"}
            conn.execute(text("""
                UPDATE source_event_crosswalk SET match_method = 'confirmed',
                       updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
            """), {"id": row_id})
        return {"ok": True}

    def reject_crosswalk_row(self, row_id: int) -> Dict[str, Any]:
        """Operator rejects a fuzzy match; the row is deleted so the source event
        resolves as unmatched (re-ingest will create its own tournament).

        Returns the linked tournament's current results count so the operator can
        verify whether gap-filled rows from the rejected source remain on it.
        """
        with self.db.engine.begin() as conn:
            row = conn.execute(text("""
                SELECT tournament_id FROM source_event_crosswalk
                WHERE id = :id AND match_method IN ('date+name', 'llm')
            """), {"id": row_id}).fetchone()
            if row is None:
                return {"ok": False, "reason": "not_found"}
            tid = row[0]
            n_results = conn.execute(
                text("SELECT COUNT(*) FROM tournament_results WHERE tournament_id = :tid"),
                {"tid": tid},
            ).scalar()
            conn.execute(
                text("DELETE FROM source_event_crosswalk WHERE id = :id"),
                {"id": row_id},
            )
        return {"ok": True, "tournament_id": tid, "local_results_count": int(n_results or 0)}

    def purge_same_source_fuzzy_duplicates(self) -> Dict[str, Any]:
        """Delete provably-wrong fuzzy rows: a source event fuzzy-mapped onto a tournament
        that the *same source* already owns under a different event id (1:1 violation).
        Safe: the canonical 'ingest' row for the tournament is never touched."""
        with self.db.engine.begin() as conn:
            res = conn.execute(text("""
                DELETE FROM source_event_crosswalk c
                WHERE c.match_method IN ('date+name', 'llm')
                  AND EXISTS (
                    SELECT 1 FROM source_event_crosswalk k
                    WHERE k.source = c.source
                      AND k.tournament_id = c.tournament_id
                      AND k.id != c.id
                      AND k.match_method NOT IN ('date+name', 'llm')
                  )
                RETURNING c.source, c.source_event_id, c.tournament_id
            """))
            deleted = [dict(r) for r in res.mappings().all()]
        return {"deleted_count": len(deleted), "deleted": deleted}

    def insidesp_drift(self, begin_year: int = 2020, end_year: Optional[int] = None) -> Dict[str, Any]:
        """Compare Inside Spin API catalog size vs local crosswalk + insidesp_* tournaments."""
        end_year = end_year or datetime.utcnow().year
        try:
            resp = requests.get(
                INSIDESP_API,
                params={"beginYear": begin_year, "endYear": end_year},
                headers={
                    "Accept": "application/json",
                    "Referer": INSIDESP_REFERER,
                    "User-Agent": "RankingsBot/1.0 (data-quality; manual)",
                },
                timeout=45,
            )
            resp.raise_for_status()
            api_rows = resp.json().get("data") or []
            api_count = len(api_rows)
            api_with_results = sum(1 for r in api_rows if int(r.get("results_count") or 0) > 0)
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc), "api_count": None}

        with self.db.engine.connect() as conn:
            is_crosswalk = conn.execute(text("""
                SELECT COUNT(*) FROM source_event_crosswalk WHERE source = 'insidesp'
            """)).scalar()
            is_history = conn.execute(text("""
                SELECT COUNT(*) FROM tournament_history WHERE tournament_id LIKE 'insidesp_%'
            """)).scalar()
            dp_crosswalk = conn.execute(text("""
                SELECT COUNT(*) FROM source_event_crosswalk WHERE source = 'digitalpool'
            """)).scalar()
            digitalpool_history = conn.execute(text(
                "SELECT COUNT(*) FROM tournament_history WHERE tournament_id LIKE 'dp_%'"
            )).scalar()

        return {
            "begin_year": begin_year,
            "end_year": end_year,
            "api_catalog_count": api_count,
            "api_with_results": api_with_results,
            "local_insidesp_crosswalk": int(is_crosswalk or 0),
            "local_insidesp_tournaments": int(is_history or 0),
            "local_digitalpool_crosswalk": int(dp_crosswalk or 0),
            "local_dp_tournaments": int(digitalpool_history or 0),
            "note": (
                "API count is full catalog; local insidesp_* is curated pro ingest only. "
                "Drift is expected until Tier-2 ingest widens scope."
            ),
        }

    def rankings_snapshot_summary(self) -> Dict[str, Any]:
        prefixes = ("InsideSpin_", "DigitalPool_", "Competitors_Pool_")
        out: Dict[str, Any] = {}
        with self.db.engine.connect() as conn:
            for prefix in prefixes:
                row = conn.execute(text("""
                    SELECT COUNT(DISTINCT ranking_system) AS systems,
                           COUNT(*) AS rows,
                           MAX(snapshot_date) AS latest
                    FROM rankings
                    WHERE ranking_system LIKE :pfx
                """), {"pfx": f"{prefix}%"}).fetchone()
                out[prefix.rstrip("_")] = {
                    "systems": int(row[0] or 0),
                    "rows": int(row[1] or 0),
                    "latest_snapshot": str(row[2]) if row[2] else None,
                }
        return out

    def fargo_coverage(self) -> Dict[str, Any]:
        with self.db.engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM players")).scalar()
            with_fargo = conn.execute(text(
                "SELECT COUNT(*) FROM players WHERE fargo_score IS NOT NULL"
            )).scalar()
            dp_linked = conn.execute(text(
                "SELECT COUNT(*) FROM players WHERE digitalpool_player_id IS NOT NULL"
            )).scalar()
        total_i = int(total or 0)
        fargo_i = int(with_fargo or 0)
        return {
            "players_total": total_i,
            "with_fargo_score": fargo_i,
            "missing_fargo_score": total_i - fargo_i,
            "digitalpool_player_id_linked": int(dp_linked or 0),
        }

    def run(
        self,
        *,
        begin_year: int = 2020,
        end_year: Optional[int] = None,
        apply_aliases: bool = False,
        alias_systems: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "crosswalk": self.crosswalk_summary(),
            "insidesp_drift": self.insidesp_drift(begin_year, end_year),
            "rankings": self.rankings_snapshot_summary(),
            "fargo_coverage": self.fargo_coverage(),
            "alias_seed": None,
        }

        if apply_aliases:
            systems = alias_systems or [
                "WPA_Men", "WPA_Women", "WPBA_Women",
                "InsideSpin_9Ball", "InsideSpin_Women",
                "Competitors_Pool_9Ball", "DigitalPool_WPAWorldMen",
            ]
            report["alias_seed"] = self._seed_aliases(systems)

        return report

    def _seed_aliases(self, systems: List[str]) -> Dict[str, Any]:
        """Run the existing seed_name_aliases_from_rankings script (SSOT)."""
        import subprocess
        import sys
        from pathlib import Path

        script = Path(__file__).resolve().parents[2] / "scripts" / "seed_name_aliases_from_rankings.py"
        if not script.is_file():
            return {"error": f"seed script missing: {script}"}
        cmd = [sys.executable, str(script), "--apply", "--systems", *systems]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(script.parents[1]),
            )
            return {
                "systems": systems,
                "exit_code": proc.returncode,
                "stdout": (proc.stdout or "")[-4000:],
                "stderr": (proc.stderr or "")[-2000:],
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc), "systems": systems}
