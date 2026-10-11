"""
Authoritative DB snapshot for Ask AI (POST /api/ai-narrative/ask).

Merges rankings/overview-style data with tournament_results so questions like
“best finish in tournament history?” are answerable from any page.

When the widget does not register a player_name, resolve_player_name_from_question()
extracts a candidate from the user question (Python re named groups) and looks up
rankings/aliases — see docs/ALFA_AI_HOW_TO_USE.md § In-app Ask AI — player DB context.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import inspect, text

from database import get_database_manager, get_db_session, get_engine

logger = logging.getLogger(__name__)

_MAX_TOURNAMENT_ROWS = 100

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
_ALFA_DEALS_FILE = _CONFIG_DIR / "alfa_deals.json"
_ALFA_KNOWLEDGE_FILE = _CONFIG_DIR / "alfa_knowledge.json"
_LOGIN_FEATURES_FILE = _CONFIG_DIR / "login_features.json"
_USPBF_KNOWLEDGE_FILE = _CONFIG_DIR / "uspbf_knowledge.json"

# Named capture group "name" — Python re docs: https://docs.python.org/3/library/re.html
_PLAYER_NAME_PATTERNS: Tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"(?:show|tell|get|give|pull|find)\s+(?:me\s+)?(?:the\s+)?"
        r"(?:stats?|statistics|info|information|data|ratings?|rankings?|performance|history|profile)\s+"
        r"(?:for|about|on|of)\s+(?P<name>[A-Za-z][A-Za-z.'\-]+(?:\s+[A-Za-z][A-Za-z.'\-]+){0,3})",
        r"(?:stats?|statistics|info|information|data|ratings?|rankings?|performance|history|profile)\s+"
        r"(?:for|about|on|of)\s+(?P<name>[A-Za-z][A-Za-z.'\-]+(?:\s+[A-Za-z][A-Za-z.'\-]+){0,3})",
        r"(?:who\s+is|what\s+about|tell\s+me\s+about|look\s+up)\s+"
        r"(?P<name>[A-Za-z][A-Za-z.'\-]+(?:\s+[A-Za-z][A-Za-z.'\-]+){0,3})",
        r"(?P<name>[A-Za-z][A-Za-z.\-]+(?:\s+[A-Za-z][A-Za-z.\-]+){1,3})(?:['\u2019]s)?\s+"
        r"(?:stats?|statistics|rating|rankings?|performance|history|record)",
    )
)

_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "my",
        "me",
        "this",
        "that",
        "player",
        "players",
        "app",
        "tier",
        "tiers",
        "pro",
        "freebie",
        "wpba",
        "wpa",
        "fargo",
        "alfa",
        "ranking",
        "rankings",
        "tournament",
        "tournaments",
        "show",
        "stats",
        "statistics",
    }
)


def _read_json_file(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("ask_ai: failed to read %s: %s", path, e)
        return None


def _filter_active_deals(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    today = datetime.now(timezone.utc).date()
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if not item.get("active", False):
            continue
        exp = item.get("expires")
        if exp:
            try:
                exp_d = date.fromisoformat(str(exp).strip()[:10])
                if exp_d < today:
                    continue
            except (TypeError, ValueError):
                logger.debug("alfa_deals: skip bad expires on %s", item.get("title"))
        out.append(
            {
                "title": item.get("title"),
                "tier": item.get("tier"),
                "discount_percent": item.get("discount_percent"),
                "deal_price": item.get("deal_price"),
                "tagline": item.get("tagline"),
                "expires": item.get("expires"),
            }
        )
    return out


def _slim_tier_catalog(effective: Dict[str, Any]) -> Dict[str, Any]:
    slim: Dict[str, Any] = {}
    for key, row in (effective or {}).items():
        if not isinstance(row, dict):
            continue
        slim[key] = {
            "name": row.get("name", key),
            "price_monthly": row.get("price_monthly"),
            "monthly_limit": row.get("monthly_limit"),
            "lifetime_limit": row.get("lifetime_limit"),
            "max_video_duration_seconds": row.get("max_video_duration"),
            "features": row.get("features") if isinstance(row.get("features"), list) else [],
        }
    return slim


def build_alfa_knowledge_bundle(current_user: dict) -> Dict[str, Any]:
    """
    Non-player context for ALFa: JWT role, AI Coach tier, tier catalog, deals, app copy.
    Safe if DB or files are missing (defaults).
    """
    role = (current_user.get("role") or "user").strip().lower()
    user_id = (current_user.get("sub") or current_user.get("username") or "").strip()

    tier_key = "FREEBIE"
    discount_percent: Optional[int] = None
    discount_expires_at: Optional[str] = None

    if user_id:
        db = None
        try:
            db = get_db_session()
            from api.models.ai_coach import AICoachUsage

            usage = db.query(AICoachUsage).filter_by(user_id=user_id).first()
            if usage and getattr(usage, "tier", None):
                tier_key = str(usage.tier).strip().upper() or "FREEBIE"
            if usage is not None:
                d = getattr(usage, "discount_percent", None)
                if d is not None and int(d) > 0:
                    discount_percent = int(d)
                de = getattr(usage, "discount_expires_at", None)
                if de is not None:
                    discount_expires_at = de.isoformat() if hasattr(de, "isoformat") else str(de)
        except Exception as e:
            logger.warning("build_alfa_knowledge_bundle: tier lookup failed: %s", e)
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

    if role == "super_admin":
        tier_key = "PRO"

    try:
        from api.config.admin_config import get_effective_tier_config

        effective = get_effective_tier_config()
    except Exception as e:
        logger.warning("build_alfa_knowledge_bundle: tier config failed: %s", e)
        effective = {}

    tier_row = effective.get(tier_key, effective.get("FREEBIE", {}))
    if not isinstance(tier_row, dict):
        tier_row = {}
    user_tier_name = str(tier_row.get("name") or tier_key)
    try:
        user_price = float(tier_row.get("price_monthly") or 0.0)
    except (TypeError, ValueError):
        user_price = 0.0

    deals_raw = _read_json_file(_ALFA_DEALS_FILE)
    active_deals = _filter_active_deals(deals_raw)

    identity = _read_json_file(_ALFA_KNOWLEDGE_FILE)
    if not isinstance(identity, dict):
        identity = {}

    lf = _read_json_file(_LOGIN_FEATURES_FILE)
    app_features: List[Any] = []
    if isinstance(lf, dict) and isinstance(lf.get("full"), list):
        app_features = lf["full"]

    tier_order = ["FREEBIE", "ROOKIE", "WEEKEND_WARRIOR", "POOL_SHARK", "PRO"]
    try:
        user_tier_index = tier_order.index(tier_key)
    except ValueError:
        user_tier_index = 0

    return {
        "user_tier": tier_key,
        "user_tier_name": user_tier_name,
        "user_price_monthly": user_price,
        "user_role": role,
        "user_tier_index": user_tier_index,
        "tier_order": tier_order,
        "account_discount_percent": discount_percent,
        "account_discount_expires_at": discount_expires_at,
        "tier_catalog": _slim_tier_catalog(effective),
        "active_deals": active_deals,
        "app_features": app_features,
        "app_identity": identity,
        "premium_notes": (
            "PRO subscription (ai_coach_usage.tier == PRO) unlocks Live Est. Rating and ALFa Rating "
            "in rankings and live tournament views; lower tiers do not. AI Coach limits follow tier_catalog."
        ),
    }


def build_demo_alfa_knowledge_bundle() -> Dict[str, Any]:
    """
    Public USPBF homepage demo: tiers, deals, app copy, and USPBF site facts — no user identity or DB tier.
    """
    try:
        from api.config.admin_config import get_effective_tier_config

        effective = get_effective_tier_config()
    except Exception as e:
        logger.warning("build_demo_alfa_knowledge_bundle: tier config failed: %s", e)
        effective = {}

    deals_raw = _read_json_file(_ALFA_DEALS_FILE)
    active_deals = _filter_active_deals(deals_raw)

    identity = _read_json_file(_ALFA_KNOWLEDGE_FILE)
    if not isinstance(identity, dict):
        identity = {}

    lf = _read_json_file(_LOGIN_FEATURES_FILE)
    app_features: List[Any] = []
    if isinstance(lf, dict) and isinstance(lf.get("full"), list):
        app_features = lf["full"]

    uspbf = _read_json_file(_USPBF_KNOWLEDGE_FILE)
    if not isinstance(uspbf, dict):
        uspbf = {}

    tier_order = ["FREEBIE", "ROOKIE", "WEEKEND_WARRIOR", "POOL_SHARK", "PRO"]

    return {
        "demo_mode": True,
        "audience": "anonymous_uspbf_homepage",
        "user_tier": "FREEBIE",
        "user_tier_name": "Visitor (demo)",
        "user_role": "anonymous",
        "user_tier_index": 0,
        "tier_order": tier_order,
        "account_discount_percent": None,
        "account_discount_expires_at": None,
        "tier_catalog": _slim_tier_catalog(effective),
        "active_deals": active_deals,
        "app_features": app_features,
        "app_identity": identity,
        "uspbf_site": uspbf,
        "premium_notes": (
            "Demo only: explain Pro Billiards Software tiers and deals from JSON; do not claim personal "
            "subscription status. For player-specific stats users must sign in at probilliardssoftware.com."
        ),
    }


def _clean_extracted_name(raw: str) -> str:
    name = (raw or "").strip().strip("\"'`")
    name = re.sub(r"[?!.]+$", "", name).strip()
    name = re.sub(r"\s+", " ", name)
    # Strip trailing possessive from last token (Allison Fisher's → Allison Fisher)
    name = re.sub(r"(?i)(['\u2019]s)\s*$", "", name).strip()
    parts = name.split()
    if parts and re.fullmatch(r"(?i).+['\u2019]s", parts[-1]):
        parts[-1] = re.sub(r"(?i)['\u2019]s$", "", parts[-1])
        name = " ".join(parts)
    return name.strip()


def extract_player_name_candidates(question: str) -> List[str]:
    """
    Extract possible player names from a free-text Ask AI question.

    Uses Python ``re`` named groups (``(?P<name>...)``) — see
    https://docs.python.org/3/library/re.html
    """
    q = (question or "").strip()
    if not q:
        return []
    out: List[str] = []
    seen: set[str] = set()

    def _add(candidate: str) -> None:
        cleaned = _clean_extracted_name(candidate)
        if not cleaned:
            return
        parts = cleaned.split()
        if len(parts) < 2 or len(parts) > 4:
            return
        if any(p.lower() in _STOPWORDS for p in parts):
            # Allow real names that include common words only if mixed case looks like a name
            if not all(p[:1].isupper() for p in parts if p):
                return
        key = cleaned.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(cleaned)

    for pattern in _PLAYER_NAME_PATTERNS:
        m = pattern.search(q)
        if m:
            _add(m.group("name"))

    # Bare "First Last" / "First Middle Last" when the whole question is mostly a name
    bare = re.fullmatch(
        r"(?P<name>[A-Za-z][A-Za-z.'\-]+(?:\s+[A-Za-z][A-Za-z.'\-]+){1,3})\??",
        q.strip(),
    )
    if bare:
        _add(bare.group("name"))

    return out


def resolve_player_name_from_question(question: str, current_user: dict) -> Optional[str]:
    """
    Resolve a player mentioned in ``question`` to a DB-known name the user may view.

    Returns None when no candidate matches rankings/aliases or access is denied
    (caller should keep answering from app/tier knowledge only — do not 403 unless
    an explicit player_name was sent and forbidden).
    """
    from api.routes import player_performance as pp

    candidates = extract_player_name_candidates(question)
    if not candidates:
        return None

    engine = get_engine()
    for candidate in candidates:
        if not pp._can_access_player(current_user, candidate):
            continue
        resolved = pp._resolve_canonical_player_name(engine, candidate)
        if not resolved:
            # Try request resolver (license/aliases) even if exact rankings miss
            resolved = pp._resolve_player_for_request(engine, candidate, current_user)
        if not resolved:
            continue
        # Confirm the resolved spelling exists or is accessible
        if not pp._can_access_player(current_user, resolved):
            continue
        # Prefer a hit that exists in rankings / tournament_results
        check = pp._resolve_canonical_player_name(engine, resolved)
        if check:
            return check
        return resolved.strip()
    return None


def _tournament_career_aggregate(names: List[str]) -> Optional[Dict[str, Any]]:
    """Best placement and win counts over all history (not limited to recent rows)."""
    uniq: List[str] = []
    seen: set[str] = set()
    for n in names:
        s = (n or "").strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            uniq.append(s)
    if not uniq:
        return None
    conn = None
    try:
        db = get_database_manager()
        conn = db.get_connection()
        cursor = conn.cursor()
        or_clause = " OR ".join(
            "LOWER(TRIM(tr.player_name)) = LOWER(TRIM(%s))" for _ in uniq
        )
        cursor.execute(
            f"""
            SELECT
                MIN(tr.placement) AS best_placement,
                COUNT(*) FILTER (WHERE tr.placement = 1) AS first_place_finishes,
                COUNT(*) FILTER (WHERE tr.placement IS NOT NULL AND tr.placement <= 3) AS top_3_finishes,
                COUNT(*) AS total_result_rows
            FROM tournament_results tr
            WHERE {or_clause}
            """,
            tuple(uniq),
        )
        row = cursor.fetchone()
        if not row or row[0] is None and row[3] == 0:
            return None
        cols = [c[0] for c in cursor.description]
        return dict(zip(cols, row))
    except Exception as e:
        logger.warning("ask_ai tournament aggregate failed: %s", e)
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _slim_tournament_row(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tournament_name": r.get("tournament_name"),
        "year": r.get("year"),
        "date": str(r.get("date") or "")[:32],
        "placement": r.get("placement"),
        "association": r.get("association"),
        "championship": r.get("championship"),
        "location": r.get("location"),
    }


def _fetch_tournament_rows_for_names(names: List[str]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Return slim rows and the player_name spelling that matched in DB (first hit)."""
    seen: set[str] = set()
    matched_as: Optional[str] = None
    conn = None
    try:
        db = get_database_manager()
        conn = db.get_connection()
        cursor = conn.cursor()
        for raw in names:
            n = (raw or "").strip()
            if not n or n.lower() in seen:
                continue
            seen.add(n.lower())
            cursor.execute(
                """
                SELECT
                    tr.placement,
                    tr.points,
                    th.name AS tournament_name,
                    th.year,
                    th.championship,
                    th.date,
                    th.association,
                    th.location,
                    tr.player_name
                FROM tournament_results tr
                JOIN tournament_history th ON tr.tournament_id = th.tournament_id
                WHERE LOWER(TRIM(tr.player_name)) = LOWER(TRIM(%s))
                ORDER BY th.date DESC NULLS LAST, th.year DESC NULLS LAST, th.name ASC
                LIMIT %s
                """,
                (n, _MAX_TOURNAMENT_ROWS),
            )
            cols = [c[0] for c in cursor.description]
            rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
            if rows:
                slim = [_slim_tournament_row(r) for r in rows]
                matched_as = rows[0].get("player_name") or n
                return slim, matched_as
        return [], None
    except Exception as e:
        logger.warning("ask_ai tournament fetch failed: %s", e)
        return [], None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def build_server_ask_ai_bundle(player_name: str, current_user: dict) -> Dict[str, Any]:
    """
    Load rankings snapshot + tournament finishes for one player.
    Caller must have already verified _can_access_player(current_user, player_name).

    Includes alfa_rating (rankings) and est_rating* (players) only when
    rankings._can_view_paid_ratings is true. Column presence is detected at runtime
    so older DBs without a column still return base stats.
    """
    from api.routes import player_performance as pp
    from api.routes.rankings import _can_view_paid_ratings

    include_paid = _can_view_paid_ratings(current_user)

    engine = get_engine()
    resolved = pp._resolve_player_for_request(engine, player_name, current_user)
    variants = pp._name_variants_for_lookup(resolved)
    if not variants:
        vn = (resolved or player_name or "").strip() or (player_name or "").strip()
        variants = [vn] if vn else []

    params = {f"v{i}": v for i, v in enumerate(variants)}
    where = pp._rankings_where_variants(variants)

    wpba = wpa_women = wpa_men = None
    tournament_stats = None
    wpba_data = wpa_women_data = wpa_men_data = None
    est_from_players: Optional[Dict[str, Any]] = None

    try:
        with engine.connect() as conn:
            rankings_cols = {c["name"] for c in inspect(conn).get_columns("rankings")}
            paid_rankings_select = ""
            if include_paid and "alfa_rating" in rankings_cols:
                paid_rankings_select = ", alfa_rating"

            wpba_data = conn.execute(
                text(
                    f"""
                    SELECT player_name, rank, points as rating, country, snapshot_date as created_at,
                           fargo_rating, fargo_last_updated, license_number, stops_played
                           {paid_rankings_select}
                    FROM rankings
                    WHERE {where} AND ranking_system = 'WPBA_Women'
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                    """
                ),
                params,
            ).mappings().first()
            wpa_women_data = conn.execute(
                text(
                    f"""
                    SELECT player_name, rank, points as rating, country, snapshot_date as created_at,
                           fargo_rating, fargo_last_updated, license_number, stops_played
                           {paid_rankings_select}
                    FROM rankings
                    WHERE {where} AND ranking_system = 'WPA_Women'
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                    """
                ),
                params,
            ).mappings().first()
            wpa_men_data = conn.execute(
                text(
                    f"""
                    SELECT player_name, rank, points as rating, country, snapshot_date as created_at,
                           fargo_rating, fargo_last_updated, license_number, stops_played
                           {paid_rankings_select}
                    FROM rankings
                    WHERE {where} AND ranking_system = 'WPA_Men'
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                    """
                ),
                params,
            ).mappings().first()
            try:
                inspector = inspect(conn)
                if "player_tournament_stats" in inspector.get_table_names(schema="public"):
                    tournament_stats = conn.execute(
                        text(
                            f"""
                            SELECT player_name, total_tournaments, first_place_finishes, top_3_finishes,
                                   total_points_earned, avg_placement, last_tournament_date
                            FROM player_tournament_stats WHERE {where}
                            """
                        ),
                        params,
                    ).mappings().first()
            except Exception:
                logger.debug("ask_ai: skip player_tournament_stats", exc_info=True)

            if include_paid:
                try:
                    player_tables = set(inspect(conn).get_table_names(schema="public"))
                    if "players" in player_tables:
                        pcols = {c["name"] for c in inspect(conn).get_columns("players")}
                        est_fields = [
                            f
                            for f in (
                                "est_rating",
                                "est_rating_confidence",
                                "est_rating_robustness",
                                "est_rating_trend",
                            )
                            if f in pcols
                        ]
                        if est_fields:
                            # Match First Last or Last, First via rankings name variants
                            name_or = " OR ".join(
                                f"LOWER(TRIM(first_name || ' ' || last_name)) = LOWER(TRIM(:v{i}))"
                                f" OR LOWER(TRIM(last_name || ', ' || first_name)) = LOWER(TRIM(:v{i}))"
                                for i in range(len(variants))
                            )
                            sel = ", ".join(est_fields)
                            est_row = conn.execute(
                                text(
                                    f"""
                                    SELECT {sel}
                                    FROM players
                                    WHERE ({name_or})
                                    LIMIT 1
                                    """
                                ),
                                params,
                            ).mappings().first()
                            if est_row:
                                est_from_players = {k: est_row[k] for k in est_fields}
                except Exception:
                    logger.debug("ask_ai: skip players.est_rating lookup", exc_info=True)

        wpba = pp._rank_row_to_dict(wpba_data)
        wpa_women = pp._rank_row_to_dict(wpa_women_data)
        wpa_men = pp._rank_row_to_dict(wpa_men_data)
        if include_paid:
            for row_dict, src in (
                (wpba, wpba_data),
                (wpa_women, wpa_women_data),
                (wpa_men, wpa_men_data),
            ):
                if not row_dict or src is None:
                    continue
                if "alfa_rating" in src:
                    row_dict["alfa_rating"] = src["alfa_rating"]
                if est_from_players:
                    row_dict.update(est_from_players)
        ts = pp._stats_row_to_dict(tournament_stats)

        def _pn(r):
            if not r:
                return None
            return r.get("player_name") if isinstance(r, dict) else getattr(r, "player_name", None)

        canonical = _pn(wpba_data) or _pn(wpa_women_data) or _pn(wpa_men_data) or resolved

        performance: Optional[Dict[str, Any]] = None
        if wpba or wpa_women or wpa_men or ts:
            performance = {
                "player_name": canonical,
                "wpba": wpba,
                "wpa_women": wpa_women,
                "wpa_men": wpa_men,
                "tournament_stats": ts,
                "paid_ratings_included": include_paid,
            }
            if include_paid and est_from_players:
                performance["live_est_rating"] = est_from_players
    except Exception as e:
        logger.warning("ask_ai performance snapshot failed: %s", e)
        performance = None
        canonical = resolved

    name_order: List[str] = []
    for x in [canonical, resolved, player_name.strip(), *(variants or [])]:
        if x and str(x).strip() and str(x).strip().lower() not in {n.lower() for n in name_order}:
            name_order.append(str(x).strip())

    tournament_rows, matched_tournament_name = _fetch_tournament_rows_for_names(name_order)
    career = _tournament_career_aggregate(name_order)

    stats_summary: Optional[Dict[str, Any]] = None
    if tournament_rows or career:
        stats_summary = {
            "recent_finishes_in_context": len(tournament_rows),
            "career_from_database": career,
            "note": (
                "Use career_from_database for best_placement and win counts across all stored results. "
                "tournament_finishes lists up to 100 recent events for examples (names, years)."
            ),
        }

    return {
        "query_name": player_name.strip(),
        "resolved_name": resolved,
        "performance": performance,
        "tournament_finishes": tournament_rows,
        "tournament_matched_as": matched_tournament_name,
        "tournament_summary": stats_summary,
        "paid_ratings_included": include_paid,
    }
