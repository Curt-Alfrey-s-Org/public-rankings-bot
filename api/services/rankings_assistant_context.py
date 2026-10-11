"""
Role-scoped JSON context for the Rankings Assistant (Ollama).

All access control is enforced here: only data that the user's role may see is included.
The model is instructed to answer only from this payload (defense in depth).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

# Tier names map to prompt policies (not stored in JWT).
# score_keeper JWT role = tablet/device in scorekeeper mode (director assigns); not an end-user "player" persona.
TierPlayer = "player"
TierScorekeeper = "scorekeeper"
TierDirector = "director"
TierAdmin = "admin"
TierSuperAdmin = "super_admin"


def assistant_tier_for_role(role: str) -> str:
    r = (role or "").strip().lower()
    if r == "super_admin":
        return TierSuperAdmin
    if r == "admin":
        return TierAdmin
    if r == "director":
        return TierDirector
    if r == "score_keeper":
        return TierScorekeeper
    # user or unknown → player-safe tier
    return TierPlayer


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_json(obj: Any, max_chars: int = 24_000) -> str:
    try:
        s = json.dumps(obj, default=str)
    except (TypeError, ValueError):
        s = "{}"
    if len(s) > max_chars:
        return s[: max_chars - 20] + "\n... [truncated]"
    return s


def _linked_player_row(engine, username: str) -> Optional[Dict[str, Any]]:
    """Return {player_name, license_number} from user_player_links if present."""
    u = (username or "").strip()
    if not u:
        return None
    try:
        with engine.connect() as conn:
            user_row = conn.execute(
                text("SELECT id FROM users WHERE username = :username"),
                {"username": u},
            ).mappings().first()
            if not user_row:
                return None
            uid = user_row.get("id")
            row = conn.execute(
                text(
                    "SELECT player_name, license_number FROM user_player_links WHERE user_id = :uid"
                ),
                {"uid": uid},
            ).mappings().first()
            if not row:
                return None
            return {
                "player_name": row.get("player_name"),
                "license_number": row.get("license_number"),
            }
    except Exception as e:
        logger.debug("linked player lookup failed: %s", e)
        return None


def _name_variants(name: str) -> List[str]:
    """Same logic as player_performance name variants (no import cycle)."""
    n = (name or "").strip()
    if not n:
        return []
    variants = [n]
    if "," in n:
        parts = [p.strip() for p in n.split(",", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            variants.append(f"{parts[1]} {parts[0]}")
    else:
        parts = [p.strip() for p in n.split() if p.strip()]
        if len(parts) >= 2:
            variants.append(f"{parts[-1]}, {' '.join(parts[:-1])}")
    return list(dict.fromkeys(v for v in variants if v))


def _top_rankings_snapshot(engine, limit: int = 5) -> Dict[str, Any]:
    systems = ("WPBA_Women", "WPA_Women", "WPA_Men")
    out: Dict[str, Any] = {}
    try:
        with engine.connect() as conn:
            for sys in systems:
                latest_row = conn.execute(
                    text("""
                        SELECT MAX(snapshot_date) AS d
                        FROM rankings
                        WHERE ranking_system = :sys
                    """),
                    {"sys": sys},
                ).mappings().first()
                latest = latest_row.get("d") if latest_row else None
                if latest is None:
                    out[sys] = {"latest_snapshot": None, "top_players": []}
                    continue
                latest_txt = str(latest)[:32]
                rows = conn.execute(
                    text("""
                        SELECT player_name, rank, points, country, snapshot_date::text AS snapshot_date
                        FROM rankings
                        WHERE ranking_system = :sys AND snapshot_date = :d
                        ORDER BY rank ASC NULLS LAST
                        LIMIT :lim
                    """),
                    {"sys": sys, "d": latest, "lim": limit},
                ).mappings().all()
                top = []
                for r in rows:
                    pn = (r.get("player_name") or "").strip()
                    if not pn:
                        continue
                    top.append(
                        {
                            "player_name": pn,
                            "rank": r.get("rank"),
                            "points": float(r["points"]) if r.get("points") is not None else None,
                            "country": r.get("country"),
                        }
                    )
                out[sys] = {"latest_snapshot": latest_txt, "top_players": top}
    except Exception as e:
        logger.warning("top rankings snapshot failed: %s", e)
        out["error"] = str(e)[:200]
    return out


def _my_tournament_aggregate(engine, canonical_name: str) -> Optional[Dict[str, Any]]:
    variants = _name_variants(canonical_name)
    if not variants:
        return None
    params = {f"v{i}": v for i, v in enumerate(variants)}
    conds = " OR ".join(
        f"LOWER(TRIM(tr.player_name)) = LOWER(TRIM(:v{i}))" for i in range(len(variants))
    )
    where_tr = f"({conds})"
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(f"""
                    SELECT
                        COUNT(*) AS events,
                        SUM(CASE WHEN tr.placement = 1 THEN 1 ELSE 0 END) AS first_place,
                        SUM(CASE WHEN tr.placement <= 3 THEN 1 ELSE 0 END) AS top_3,
                        AVG(tr.placement) AS avg_placement,
                        SUM(tr.points) AS total_points
                    FROM tournament_results tr
                    JOIN tournament_history th ON tr.tournament_id = th.tournament_id
                    WHERE {where_tr} AND th.date IS NOT NULL
                """),
                params,
            ).mappings().first()
            if not row or not row.get("events"):
                return {"events": 0, "note": "no tournament rows in history for linked player"}
            return {
                "events": int(row["events"] or 0),
                "first_place": int(row["first_place"] or 0),
                "top_3": int(row["top_3"] or 0),
                "avg_placement": float(row["avg_placement"]) if row.get("avg_placement") is not None else None,
                "total_points": float(row["total_points"]) if row.get("total_points") is not None else None,
            }
    except Exception as e:
        logger.debug("tournament aggregate failed: %s", e)
        return None


def _recent_tournaments(engine, limit: int = 12) -> List[Dict[str, Any]]:
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT name, date::text AS date, association, location
                    FROM tournament_history
                    WHERE date IS NOT NULL
                    ORDER BY date DESC
                    LIMIT :lim
                """),
                {"lim": limit},
            ).mappings().all()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("recent tournaments failed: %s", e)
        return []


def _upcoming_events_slice(engine, limit: int = 10) -> List[Dict[str, Any]]:
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            if "upcoming_events" not in inspector.get_table_names(schema="public"):
                return []
            rows = conn.execute(
                text("""
                    SELECT name, event_date::text AS event_date, association, location
                    FROM upcoming_events
                    ORDER BY event_date ASC NULLS LAST
                    LIMIT :lim
                """),
                {"lim": limit},
            ).mappings().all()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.debug("upcoming_events slice failed: %s", e)
        return []


def _director_clocks() -> Dict[str, Any]:
    try:
        from api.routes.director import CLOCK_SETTINGS_FILE, DEFAULTS

        out = dict(DEFAULTS)
        if CLOCK_SETTINGS_FILE.is_file():
            with open(CLOCK_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            out.update({k: data.get(k, v) for k, v in DEFAULTS.items()})
        return out
    except Exception as e:
        logger.debug("director clocks read failed: %s", e)
        return {}


def _users_by_role(engine) -> Dict[str, int]:
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT role, COUNT(*) AS n FROM users GROUP BY role")
            ).mappings().all()
            return {str(r["role"]): int(r["n"]) for r in rows if r.get("role")}
    except Exception as e:
        logger.warning("users_by_role failed: %s", e)
        return {}


def _ranking_snapshot_meta(engine) -> Dict[str, Any]:
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT ranking_system, MAX(snapshot_date)::text AS latest
                    FROM rankings
                    GROUP BY ranking_system
                """)
            ).mappings().all()
            return {r["ranking_system"]: r.get("latest") for r in rows}
    except Exception as e:
        logger.debug("ranking snapshot meta failed: %s", e)
        return {}


def build_assistant_context(
    *,
    role: str,
    username: str,
    engine,
) -> Tuple[str, Dict[str, Any], List[str]]:
    """
    Returns (tier, context_dict, list of top-level keys included).
    """
    tier = assistant_tier_for_role(role)
    keys: List[str] = []
    ctx: Dict[str, Any] = {
        "generated_at_utc": _utc_now_iso(),
        "viewer": {"username": username, "role": role, "assistant_tier": tier},
    }
    keys.append("viewer")

    ctx["public_rankings"] = _top_rankings_snapshot(engine)
    keys.append("public_rankings")

    # Player-linked stats: only for this user (same idea as player performance self)
    link = _linked_player_row(engine, username)
    if link and link.get("player_name"):
        ctx["your_player_link"] = {
            "player_name": link.get("player_name"),
            "has_license": bool(link.get("license_number")),
        }
        keys.append("your_player_link")
        agg = _my_tournament_aggregate(engine, link["player_name"])
        if agg is not None:
            ctx["your_tournament_history_summary"] = agg
            keys.append("your_tournament_history_summary")
    else:
        ctx["your_player_link"] = None
        keys.append("your_player_link")

    if tier in (TierDirector, TierScorekeeper, TierAdmin, TierSuperAdmin):
        ctx["recent_past_tournaments"] = _recent_tournaments(engine)
        keys.append("recent_past_tournaments")
        ctx["upcoming_events_sample"] = _upcoming_events_slice(engine)
        keys.append("upcoming_events_sample")
        try:
            ctx["director_clock_settings"] = _director_clocks()
            keys.append("director_clock_settings")
        except Exception:
            pass

    if tier in (TierAdmin, TierSuperAdmin):
        ctx["user_counts_by_role"] = _users_by_role(engine)
        keys.append("user_counts_by_role")
        ctx["ranking_snapshot_dates_by_system"] = _ranking_snapshot_meta(engine)
        keys.append("ranking_snapshot_dates_by_system")

    if tier == TierSuperAdmin:
        ctx["environment_flags"] = {
            "ollama_enabled": os.getenv("OLLAMA_ENABLED", "").lower() in ("true", "1", "yes"),
            "debug_mode": os.getenv("DEBUG", "").lower() in ("1", "true", "yes"),
        }
        keys.append("environment_flags")

    return tier, ctx, keys


def system_prompt_for_tier(tier: str) -> str:
    base = """You are the in-app Rankings Assistant for a billiards rankings web application.

STRICT RULES:
- Answer ONLY using facts present in the JSON block labeled CONTEXT_JSON in the user message.
- If the answer is not supported by CONTEXT_JSON, say you do not have that information in the current session. Do not guess.
- Use plain, factual language. No sports hype or invented trends.
- Never ask the user for passwords, API keys, or secrets. Never output credentials.
- Do not claim you can run shell commands, change the database, or access systems not described in CONTEXT_JSON.

ROLE SCOPE:
"""
    if tier == TierPlayer:
        return (
            base
            + "- The viewer is a PLAYER (end user): public leaderboard snapshots, their linked player name (if any), and their own tournament history summary only.\n"
            + "- Do not discuss other users' accounts, emails, or private mappings.\n"
            + "- You may explain rankings and their own stats from CONTEXT_JSON.\n"
        )
    if tier == TierScorekeeper:
        return (
            base
            + "- The viewer is a TABLET OR DEVICE running in SCOREKEEPER MODE: a tournament director assigns this mode for score entry at a table. This is not a personal player account.\n"
            + "- CONTEXT matches operational needs: public ranking snapshots, optional linked-player summary if this login has a mapping, plus recent tournaments, upcoming events sample, and director clock settings.\n"
            + "- Do not imply the device \"is\" a human player. Do not disclose admin-only aggregates unless present in CONTEXT_JSON.\n"
        )
    if tier == TierDirector:
        return (
            base
            + "- The viewer is a TOURNAMENT DIRECTOR: everything in the player tier, plus recent past tournaments, upcoming events sample, and director clock settings.\n"
            + "- Directors control which devices use scorekeeper mode; the assistant does not change roles or assignments.\n"
            + "- Do not disclose per-user admin data (counts are only provided if present in CONTEXT_JSON).\n"
        )
    if tier == TierAdmin:
        return (
            base
            + "- The viewer is an ADMIN: director-level data plus aggregate user counts by role and ranking snapshot dates by system.\n"
            + "- Do not invent user lists, emails, or passwords. Only use aggregates given.\n"
        )
    return (
        base
        + "- The viewer is SUPER ADMIN: the broadest CONTEXT_JSON provided (including environment flags).\n"
        + "- Still only use CONTEXT_JSON; do not fabricate infrastructure details.\n"
    )
