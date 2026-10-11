"""
Live Odds Engine — in-match win probability (Phase 3).

Recomputes match win odds from current score state + player ratings.
Uses Elo rack-win probability (scale 400, same as Fargo / LiveRatingEngine)
and a race-to DP for remaining games.

Doc refs (AI / maintainers): docs/ROADMAP.md § Live Est. Rating + Live Odds Phase 3
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional

logger = logging.getLogger(__name__)

FORMULA_VERSION = "live_odds_v1"
ELO_SCALE = 400.0
DEFAULT_RATING = 500.0
MAX_RACE = 64  # safety bound for DP


def rack_win_prob(rating_p1: float, rating_p2: float) -> float:
    """P(operator wins a single rack) under Elo scale 400."""
    return 1.0 / (1.0 + 10.0 ** ((rating_p2 - rating_p1) / ELO_SCALE))


def match_win_prob(
    s1: int,
    s2: int,
    race1: int,
    race2: int,
    p_rack: float,
) -> tuple[float, float]:
    """
    P(operator wins the match | current scores) given race targets and per-rack P.

    Independent rack outcomes; first to race1 / race2 wins.
    """
    race1 = max(1, min(int(race1), MAX_RACE))
    race2 = max(1, min(int(race2), MAX_RACE))
    s1 = max(0, int(s1))
    s2 = max(0, int(s2))
    p_rack = max(0.0, min(1.0, float(p_rack)))

    if s1 >= race1 and s2 >= race2:
        # Ambiguous finished state — treat as split (should not happen)
        return 0.5, 0.5
    if s1 >= race1:
        return 1.0, 0.0
    if s2 >= race2:
        return 0.0, 1.0

    # Discrete P so lru_cache is stable
    p_key = int(round(p_rack * 1_000_000))
    p1 = _dp_match_win(s1, s2, race1, race2, p_key)
    p1 = max(0.0, min(1.0, p1))
    return p1, 1.0 - p1


@lru_cache(maxsize=50_000)
def _dp_match_win(s1: int, s2: int, race1: int, race2: int, p_key: int) -> float:
    p = p_key / 1_000_000.0
    if s1 >= race1:
        return 1.0
    if s2 >= race2:
        return 0.0
    return p * _dp_match_win(s1 + 1, s2, race1, race2, p_key) + (1.0 - p) * _dp_match_win(
        s1, s2 + 1, race1, race2, p_key
    )


@dataclass
class LiveOddsResult:
    match_id: str
    tournament_id: Optional[str]
    operator_id: Optional[str]
    player2_id: Optional[str]
    p1_score: int
    p2_score: int
    race_to: Optional[int]
    p1_race: int
    p2_race: int
    p1_rating_used: float
    p2_rating_used: float
    rating_source: str
    p_rack_p1: float
    p1_win_prob: float
    p2_win_prob: float
    trigger: str
    game_id: Optional[int]
    formula_version: str
    context: dict[str, Any]
    status: Optional[str]


class LiveOddsEngine:
    """Compute and persist in-match odds snapshots."""

    def __init__(self, db_manager: Any):
        self.db = db_manager

    def _get_connection(self):
        return self.db.get_connection()

    def _player_ratings(
        self, operator_id: Optional[str], player2_id: Optional[str]
    ) -> tuple[float, float, str]:
        """Return (r1, r2, source) preferring est_rating then fargo_score."""
        if not operator_id or not player2_id:
            return DEFAULT_RATING, DEFAULT_RATING, "default"

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT player_id, est_rating, fargo_score
                FROM players
                WHERE player_id IN (%s, %s)
                """,
                (operator_id, player2_id),
            )
            rows = {str(r[0]): (r[1], r[2]) for r in cur.fetchall()}
        finally:
            conn.close()

        def pick(pid: str) -> tuple[Optional[float], Optional[float]]:
            est, fargo = rows.get(str(pid), (None, None))
            est_f = float(est) if est is not None else None
            fargo_f = float(fargo) if fargo is not None else None
            return est_f, fargo_f

        e1, f1 = pick(operator_id)
        e2, f2 = pick(player2_id)

        sources: list[str] = []
        if e1 is not None:
            r1 = e1
            sources.append("est")
        elif f1 is not None:
            r1 = f1
            sources.append("fargo")
        else:
            r1 = DEFAULT_RATING
            sources.append("default")

        if e2 is not None:
            r2 = e2
            sources.append("est")
        elif f2 is not None:
            r2 = f2
            sources.append("fargo")
        else:
            r2 = DEFAULT_RATING
            sources.append("default")

        uniq = set(sources)
        if uniq == {"est"}:
            rating_source = "est"
        elif uniq == {"fargo"}:
            rating_source = "fargo"
        elif "est" in uniq and "fargo" in uniq:
            rating_source = "mixed"
        elif uniq == {"default"}:
            rating_source = "default"
        else:
            rating_source = "mixed"

        return r1, r2, rating_source

    def _load_match(self, match_id: str) -> Optional[dict[str, Any]]:
        if hasattr(self.db, "get_match"):
            m = self.db.get_match(match_id)
            if m:
                return dict(m) if not isinstance(m, dict) else m

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT match_id, tournament_id, operator_id, player2_id,
                       operator_score, player2_score, race_to, status, winner_id,
                       operator_handicapped_race, player2_handicapped_race
                FROM matches WHERE match_id = %s
                """,
                (match_id,),
            )
            row = cur.fetchone()
            if not row:
                # older schema without handicap columns
                cur.execute(
                    """
                    SELECT match_id, tournament_id, operator_id, player2_id,
                           operator_score, player2_score, race_to, status, winner_id
                    FROM matches WHERE match_id = %s
                    """,
                    (match_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                cols = [
                    "match_id",
                    "tournament_id",
                    "operator_id",
                    "player2_id",
                    "operator_score",
                    "player2_score",
                    "race_to",
                    "status",
                    "winner_id",
                ]
                return dict(zip(cols, row))
            cols = [
                "match_id",
                "tournament_id",
                "operator_id",
                "player2_id",
                "operator_score",
                "player2_score",
                "race_to",
                "status",
                "winner_id",
                "operator_handicapped_race",
                "player2_handicapped_race",
            ]
            return dict(zip(cols, row))
        except Exception as exc:
            logger.warning("live_odds: load match %s failed: %s", match_id, exc)
            return None
        finally:
            conn.close()

    def compute_for_match(
        self,
        match_id: str,
        *,
        trigger: str = "score_update",
        game_id: Optional[int] = None,
        extra_context: Optional[dict[str, Any]] = None,
    ) -> Optional[LiveOddsResult]:
        match = self._load_match(match_id)
        if not match:
            logger.warning("live_odds: match not found %s", match_id)
            return None

        p1_id = match.get("operator_id")
        p2_id = match.get("player2_id")
        if not p1_id or not p2_id:
            return None

        s1 = int(match.get("operator_score") or 0)
        s2 = int(match.get("player2_score") or 0)
        race_to = match.get("race_to")
        race_default = int(race_to) if race_to is not None else 7
        p1_race = match.get("operator_handicapped_race")
        p2_race = match.get("player2_handicapped_race")
        r1_target = int(p1_race) if p1_race is not None else race_default
        r2_target = int(p2_race) if p2_race is not None else race_default

        r1, r2, rating_source = self._player_ratings(str(p1_id), str(p2_id))
        p_rack = rack_win_prob(r1, r2)

        status = (match.get("status") or "").lower()
        winner_id = match.get("winner_id")

        if status == "completed" or winner_id:
            if winner_id and str(winner_id) == str(p1_id):
                p1_prob, p2_prob = 1.0, 0.0
            elif winner_id and str(winner_id) == str(p2_id):
                p1_prob, p2_prob = 0.0, 1.0
            else:
                p1_prob, p2_prob = match_win_prob(s1, s2, r1_target, r2_target, p_rack)
        else:
            p1_prob, p2_prob = match_win_prob(s1, s2, r1_target, r2_target, p_rack)

        ctx: dict[str, Any] = {
            "status": match.get("status"),
            "winner_id": winner_id,
        }
        if extra_context:
            ctx.update(extra_context)

        return LiveOddsResult(
            match_id=str(match_id),
            tournament_id=str(match["tournament_id"]) if match.get("tournament_id") else None,
            operator_id=str(p1_id),
            player2_id=str(p2_id),
            p1_score=s1,
            p2_score=s2,
            race_to=int(race_to) if race_to is not None else None,
            p1_race=r1_target,
            p2_race=r2_target,
            p1_rating_used=r1,
            p2_rating_used=r2,
            rating_source=rating_source,
            p_rack_p1=p_rack,
            p1_win_prob=p1_prob,
            p2_win_prob=p2_prob,
            trigger=trigger,
            game_id=game_id,
            formula_version=FORMULA_VERSION,
            context=ctx,
            status=match.get("status"),
        )

    def record_snapshot(self, result: LiveOddsResult) -> bool:
        """Persist snapshot; best-effort denorm on matches if columns exist."""
        params = (
            result.match_id,
            result.tournament_id,
            result.operator_id,
            result.player2_id,
            result.p1_score,
            result.p2_score,
            result.race_to,
            result.p1_race,
            result.p2_race,
            result.p1_rating_used,
            result.p2_rating_used,
            result.rating_source,
            result.p_rack_p1,
            result.p1_win_prob,
            result.p2_win_prob,
            result.trigger,
            result.game_id,
            result.formula_version,
            json.dumps(result.context),
        )
        insert_sql = """
            INSERT INTO live_odds_snapshots (
                match_id, tournament_id, operator_id, player2_id,
                p1_score, p2_score, race_to, p1_race, p2_race,
                p1_rating_used, p2_rating_used, rating_source,
                p_rack_p1, p1_win_prob, p2_win_prob,
                odds_trigger, game_id, formula_version, context
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s::jsonb
            )
        """
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(insert_sql, params)
            conn.commit()
        except Exception as e:
            logger.error("live_odds: failed to record snapshot for %s: %s", result.match_id, e)
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            return False

        # Separate transaction for optional denorm columns
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE matches SET
                    live_p1_win_prob = %s,
                    live_p2_win_prob = %s,
                    odds_updated_at = %s
                WHERE match_id = %s
                """,
                (
                    result.p1_win_prob,
                    result.p2_win_prob,
                    datetime.now(timezone.utc),
                    result.match_id,
                ),
            )
            conn.commit()
        except Exception as denorm_err:
            logger.debug("live_odds denorm skip: %s", denorm_err)
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return True

    def process_match(
        self,
        match_id: str,
        *,
        trigger: str = "score_update",
        game_id: Optional[int] = None,
        extra_context: Optional[dict[str, Any]] = None,
        persist: bool = True,
    ) -> Optional[dict[str, Any]]:
        result = self.compute_for_match(
            match_id, trigger=trigger, game_id=game_id, extra_context=extra_context
        )
        if not result:
            return None
        if persist:
            self.record_snapshot(result)
        return self.result_to_dict(result)

    @staticmethod
    def result_to_dict(result: LiveOddsResult) -> dict[str, Any]:
        return {
            "match_id": result.match_id,
            "tournament_id": result.tournament_id,
            "operator_id": result.operator_id,
            "player2_id": result.player2_id,
            "p1_score": result.p1_score,
            "p2_score": result.p2_score,
            "race_to": result.race_to,
            "p1_race": result.p1_race,
            "p2_race": result.p2_race,
            "p1_rating_used": result.p1_rating_used,
            "p2_rating_used": result.p2_rating_used,
            "rating_source": result.rating_source,
            "p_rack_p1": result.p_rack_p1,
            "p1_win_prob": result.p1_win_prob,
            "p2_win_prob": result.p2_win_prob,
            "trigger": result.trigger,
            "game_id": result.game_id,
            "formula_version": result.formula_version,
            "status": result.status,
            "context": result.context,
        }

    def get_latest(self, match_id: str) -> Optional[dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT match_id, tournament_id, operator_id, player2_id,
                       p1_score, p2_score, race_to, p1_race, p2_race,
                       p1_rating_used, p2_rating_used, rating_source,
                       p_rack_p1, p1_win_prob, p2_win_prob,
                       odds_trigger, game_id, formula_version, context, created_at
                FROM live_odds_snapshots
                WHERE match_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (match_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            keys = [
                "match_id",
                "tournament_id",
                "operator_id",
                "player2_id",
                "p1_score",
                "p2_score",
                "race_to",
                "p1_race",
                "p2_race",
                "p1_rating_used",
                "p2_rating_used",
                "rating_source",
                "p_rack_p1",
                "p1_win_prob",
                "p2_win_prob",
                "trigger",
                "game_id",
                "formula_version",
                "context",
                "created_at",
            ]
            out = dict(zip(keys, row))
            if out.get("created_at") is not None:
                out["created_at"] = out["created_at"].isoformat()
            if isinstance(out.get("context"), str):
                try:
                    out["context"] = json.loads(out["context"])
                except json.JSONDecodeError:
                    pass
            return out
        except Exception as e:
            logger.warning("live_odds get_latest failed: %s", e)
            return None
        finally:
            conn.close()

    def get_history(self, match_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT match_id, p1_score, p2_score, p1_win_prob, p2_win_prob,
                       p_rack_p1, odds_trigger, game_id, formula_version, rating_source,
                       created_at
                FROM live_odds_snapshots
                WHERE match_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (match_id, max(1, min(limit, 200))),
            )
            rows = cur.fetchall()
            out = []
            for r in rows:
                item = {
                    "match_id": r[0],
                    "p1_score": r[1],
                    "p2_score": r[2],
                    "p1_win_prob": r[3],
                    "p2_win_prob": r[4],
                    "p_rack_p1": r[5],
                    "trigger": r[6],
                    "game_id": r[7],
                    "formula_version": r[8],
                    "rating_source": r[9],
                    "created_at": r[10].isoformat() if r[10] else None,
                }
                out.append(item)
            return out
        except Exception as e:
            logger.warning("live_odds get_history failed: %s", e)
            return []
        finally:
            conn.close()


def recompute_and_broadcast_live_odds(
    tm: Any,
    match_id: str,
    *,
    trigger: str = "score_update",
    game_id: Optional[int] = None,
    extra_context: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """Shared hook for rack / score / outcome paths. Never raises to callers."""
    try:
        engine = LiveOddsEngine(tm)
        odds = engine.process_match(
            match_id,
            trigger=trigger,
            game_id=game_id,
            extra_context=extra_context,
            persist=True,
        )
        return odds
    except Exception as e:
        logger.warning("recompute_and_broadcast_live_odds failed for %s: %s", match_id, e)
        return None
