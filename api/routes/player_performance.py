"""
Player Performance API Routes. Uses shared Postgres engine.
Access: admin and super_admin see all; director and user only their own (player_name matches username).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
import logging
import re
import sys

from sqlalchemy import inspect, text

from project_root import PROJECT_ROOT
sys.path.insert(0, str(PROJECT_ROOT))

from database import get_engine, get_database_manager
from api.auth import get_current_user
import os

router = APIRouter(prefix="/api/player-performance", tags=["player-performance"])
logger = logging.getLogger(__name__)

AUTO_POPULATE_ALIASES = os.getenv("AUTO_POPULATE_PLAYER_ALIASES", "false").lower() in ("true", "1", "yes")


def _get_linked_player_name(current_user: dict) -> Optional[str]:
    """Return mapped player name for a user (if mapping exists)."""
    info = _get_linked_player_info(current_user)
    return info.get("player_name") if info else None


def _get_linked_player_info(current_user: dict) -> Optional[Dict[str, str]]:
    """Return mapped player info for a user (if mapping exists)."""
    sub = (current_user.get("sub") or "").strip()
    if not sub:
        return None
    engine = get_engine()
    try:
        with engine.connect() as conn:
            user_row = conn.execute(
                text("SELECT id FROM users WHERE username = :username"),
                {"username": sub},
            ).mappings().first()
        if not user_row:
            return None
        user_id = user_row.get("id") if isinstance(user_row, dict) else getattr(user_row, "id", None)
        if not user_id:
            return None
        with engine.connect() as conn:
            mapped = conn.execute(
                text("SELECT player_name, license_number FROM user_player_links WHERE user_id = :user_id"),
                {"user_id": user_id},
            ).mappings().first()
        if not mapped:
            return None
        return {
            "player_name": mapped.get("player_name") if isinstance(mapped, dict) else getattr(mapped, "player_name", None),
            "license_number": mapped.get("license_number") if isinstance(mapped, dict) else getattr(mapped, "license_number", None),
        }
    except Exception as e:
        logger.warning("Could not resolve linked player info for current user: %s", e)
        return None


def _can_access_player(current_user: dict, player_name: str) -> bool:
    """Admin and super_admin see all; director and user only when mapped or username matches."""
    role = (current_user.get("role") or "").strip().lower()
    if role in ("admin", "super_admin"):
        return True
    sub = (current_user.get("sub") or "").strip().lower()
    pn = (player_name or "").strip().lower()
    if pn == sub:
        return True
    linked = (_get_linked_player_name(current_user) or "").strip().lower()
    if not linked:
        return False
    if linked == pn:
        return True
    vp = {v.lower() for v in _name_variants_for_lookup(player_name)}
    vl = {v.lower() for v in _name_variants_for_lookup(linked)}
    return bool(vp and vl and (vp & vl))


def _name_variants_for_lookup(name: str) -> List[str]:
    """Return variants for DB lookup: 'First Last' and 'Last, First' (scraped data often uses both)."""
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


def _normalize_license_number(license_number: Any) -> Optional[str]:
    """Normalize license for lookup (matches postgres_manager logic)."""
    raw = str(license_number or "").strip().upper()
    if not raw:
        return None
    raw = re.sub(r"\s+", " ", raw)
    m = re.search(r"([A-Z]{2,5}\s*-\s*\d{2,5})", raw)
    if m:
        return re.sub(r"\s*-\s*", " - ", m.group(1))
    if re.match(r"^[A-Z]{2,5}$", raw) or re.match(r"^\d{4,}$", raw):
        return None
    return re.sub(r"\s*-\s*", " - ", raw)


def _resolve_by_license(engine, license_number: str) -> Optional[str]:
    """Resolve canonical player_name by license_number."""
    if not license_number:
        return None
    normalized = _normalize_license_number(license_number)
    if not normalized:
        normalized = str(license_number or "").strip()
    if not normalized:
        return None
    try:
        with engine.connect() as conn:
            r = conn.execute(
                text("SELECT player_name FROM rankings WHERE license_number IS NOT NULL AND LOWER(TRIM(license_number)) = LOWER(TRIM(:lic)) LIMIT 1"),
                {"lic": normalized},
            ).mappings().first()
            if r:
                return r.get("player_name") if isinstance(r, dict) else getattr(r, "player_name", None)
    except Exception as e:
        logger.warning("Could not resolve player by license %s: %s", license_number, e)
    return None


def _resolve_canonical_player_name(engine, player_name: str) -> Optional[str]:
    """Return canonical player_name from DB (license-first, then aliases, then variants)."""
    name = (player_name or "").strip()
    if not name:
        return None

    # 1. Try aliases first (scraped_name -> canonical_name); try input and variants
    alias_variants = _name_variants_for_lookup(name)
    if not alias_variants:
        alias_variants = [name]
    try:
        with engine.connect() as conn:
            for v in alias_variants:
                alias_row = conn.execute(
                    text("SELECT canonical_name FROM player_name_aliases WHERE LOWER(TRIM(scraped_name)) = LOWER(TRIM(:name)) LIMIT 1"),
                    {"name": v},
                ).mappings().first()
                if alias_row:
                    canonical = alias_row.get("canonical_name") if isinstance(alias_row, dict) else getattr(alias_row, "canonical_name", None)
                    if canonical:
                        return canonical
    except Exception as e:
        logger.debug("Alias lookup failed for %s: %s", name, e)

    # 2. Try variants in rankings and tournament_results
    variants = _name_variants_for_lookup(name)
    if not variants:
        variants = [name]
    try:
        with engine.connect() as conn:
            for v in variants:
                r = conn.execute(
                    text("SELECT player_name, ranking_system FROM rankings WHERE LOWER(TRIM(player_name)) = LOWER(TRIM(:name)) LIMIT 1"),
                    {"name": v},
                ).mappings().first()
                if r:
                    canonical = r.get("player_name") if isinstance(r, dict) else getattr(r, "player_name", None)
                    if canonical and AUTO_POPULATE_ALIASES and name.lower() != (canonical or "").lower():
                        try:
                            system = r.get("ranking_system") if isinstance(r, dict) else getattr(r, "ranking_system", None) or "WPA_Women"
                            conn.execute(
                                text("""
                                    INSERT INTO player_name_aliases (scraped_name, canonical_name, ranking_system)
                                    VALUES (:scraped, :canonical, :system)
                                    ON CONFLICT (scraped_name, ranking_system) DO UPDATE SET canonical_name = EXCLUDED.canonical_name
                                """),
                                {"scraped": name, "canonical": canonical, "system": system},
                            )
                            conn.commit()
                        except Exception as ae:
                            logger.debug("Auto-populate alias failed for %s: %s", name, ae)
                    return canonical
                r = conn.execute(
                    text("SELECT player_name FROM tournament_results WHERE LOWER(TRIM(player_name)) = LOWER(TRIM(:name)) LIMIT 1"),
                    {"name": v},
                ).mappings().first()
                if r:
                    canonical = r.get("player_name") if isinstance(r, dict) else getattr(r, "player_name", None)
                    if canonical and AUTO_POPULATE_ALIASES and name.lower() != (canonical or "").lower():
                        try:
                            conn.execute(
                                text("""
                                    INSERT INTO player_name_aliases (scraped_name, canonical_name, ranking_system)
                                    VALUES (:scraped, :canonical, :system)
                                    ON CONFLICT (scraped_name, ranking_system) DO UPDATE SET canonical_name = EXCLUDED.canonical_name
                                """),
                                {"scraped": name, "canonical": canonical, "system": "WPA_Women"},
                            )
                            conn.commit()
                        except Exception as ae:
                            logger.debug("Auto-populate alias failed for %s: %s", name, ae)
                    return canonical
    except Exception as e:
        logger.warning("Could not resolve canonical player name for %s: %s", name, e)
    return name


def get_db_connection():
    """Shared rankings connection (DATABASE_URL)."""
    return get_engine().raw_connection()


@router.get("/me")
async def get_my_player(current_user: dict = Depends(get_current_user)):
    """Return the current user's mapped player name (or username if no player mapping exists)."""
    sub = (current_user.get("sub") or "").strip()
    mapped_info = _get_linked_player_info(current_user)

    # License-first resolution: if we have a license, resolve via license
    if mapped_info and mapped_info.get("license_number"):
        engine = get_engine()
        resolved_name = _resolve_by_license(engine, mapped_info["license_number"])
        if resolved_name:
            return {
                "player_name": resolved_name,
                "source": "license_mapping",
                "license_number": mapped_info["license_number"],
            }

    # Fall back to mapped player name, then username
    mapped_name = mapped_info.get("player_name") if mapped_info else None
    return {
        "player_name": mapped_name or sub,
        "source": "mapping" if mapped_name else "username",
        "license_number": mapped_info.get("license_number") if mapped_info else None,
    }



def _row_to_dict(row) -> Optional[Dict[str, Any]]:
    """Build dict from a row that has .keys() and index access (e.g. _RowLike)."""
    if not row:
        return None
    try:
        if hasattr(row, "keys") and callable(row.keys):
            return {key: row[key] for key in row.keys()}
    except (IndexError, KeyError, TypeError) as e:
        logger.warning("Failed to read row mapping keys for performance payload: %s", e)
    return None


def _rank_row_to_dict(row) -> Optional[Dict[str, Any]]:
    """Build dict from rankings row; include fargo_rating and fargo_last_updated when present."""
    d = _row_to_dict(row)
    if d is None and row is not None:
        try:
            d = {
                "player_name": row[0], "rank": row[1], "rating": row[2], "country": row[3] if len(row) > 3 else None,
                "created_at": str(row[4]) if len(row) > 4 and row[4] else None,
                "fargo_rating": row[5] if len(row) > 5 else None,
                "fargo_last_updated": str(row[6]) if len(row) > 6 and row[6] else None,
                "license_number": row[7] if len(row) > 7 else None,
                "stops_played": row[8] if len(row) > 8 else None,
            }
        except (IndexError, TypeError):
            return None

    # Always ensure license_number and stops_played are included
    if d is not None:
        d["license_number"] = d.get("license_number")
        d["stops_played"] = d.get("stops_played")

    return d


def _stats_row_to_dict(row) -> Optional[Dict[str, Any]]:
    """Build dict from player_tournament_stats row."""
    return _row_to_dict(row)


def _rankings_where_variants(variants: List[str]) -> str:
    """Build WHERE clause for LOWER(TRIM(player_name)) matching any variant."""
    if not variants:
        return "1=0"
    conds = " OR ".join(f"LOWER(TRIM(player_name)) = LOWER(TRIM(:v{i}))" for i in range(len(variants)))
    return f"({conds})"


def _resolve_player_for_request(engine, player_name: str, current_user: dict) -> str:
    """Resolve player_name to canonical form: license-first when own data, else aliases+variants."""
    if not player_name or not (player_name or "").strip():
        return player_name or ""
    name = (player_name or "").strip()
    if _can_access_player(current_user, name):
        info = _get_linked_player_info(current_user)
        if info and info.get("license_number"):
            resolved = _resolve_by_license(engine, info["license_number"])
            if resolved:
                return resolved
    return _resolve_canonical_player_name(engine, name) or name


@router.get("/{player_name}/overview")
async def get_player_overview(player_name: str, current_user: dict = Depends(get_current_user)):
    """Get player overview. Admin/super_admin: any player; director/user: only own (username matches player_name). Includes Fargo when available."""
    if not _can_access_player(current_user, player_name):
        raise HTTPException(status_code=403, detail="You can only view your own player performance. Other players' charts are a paid perk.")
    engine = get_engine()
    resolved_name = _resolve_player_for_request(engine, player_name, current_user)
    variants = _name_variants_for_lookup(resolved_name)
    if not variants:
        variants = [resolved_name or player_name.strip()]
    params = {f"v{i}": v for i, v in enumerate(variants)}
    where = _rankings_where_variants(variants)
    try:
        with engine.connect() as conn:
            wpba_data = conn.execute(
                text(f"""
                    SELECT player_name, rank, points as rating, country, snapshot_date as created_at, fargo_rating, fargo_last_updated, license_number, stops_played
                    FROM rankings
                    WHERE {where} AND ranking_system = 'WPBA_Women'
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                """),
                params,
            ).mappings().first()
            wpa_women_data = conn.execute(
                text(f"""
                    SELECT player_name, rank, points as rating, country, snapshot_date as created_at, fargo_rating, fargo_last_updated, license_number, stops_played
                    FROM rankings
                    WHERE {where} AND ranking_system = 'WPA_Women'
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                """),
                params,
            ).mappings().first()
            wpa_men_data = conn.execute(
                text(f"""
                    SELECT player_name, rank, points as rating, country, snapshot_date as created_at, fargo_rating, fargo_last_updated, license_number, stops_played
                    FROM rankings
                    WHERE {where} AND ranking_system = 'WPA_Men'
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                """),
                params,
            ).mappings().first()
            tournament_stats = None
            try:
                inspector = inspect(conn)
                if "player_tournament_stats" in inspector.get_table_names(schema="public"):
                    tournament_stats = conn.execute(
                        text(f"""
                            SELECT player_name, total_tournaments, first_place_finishes, top_3_finishes,
                                   total_points_earned, avg_placement, last_tournament_date
                            FROM player_tournament_stats WHERE {where}
                        """),
                        params,
                    ).mappings().first()
            except Exception:
                logger.warning("Could not read player_tournament_stats table; continuing without stats", exc_info=True)
        if not wpba_data and not wpa_women_data and not wpa_men_data:
            raise HTTPException(status_code=404, detail=f"Player '{player_name}' not found")
        wpba = _rank_row_to_dict(wpba_data)
        wpa_women = _rank_row_to_dict(wpa_women_data)
        wpa_men = _rank_row_to_dict(wpa_men_data)
        ts = _stats_row_to_dict(tournament_stats)
        def _pn(r):
            if not r: return None
            return r.get("player_name") if isinstance(r, dict) else getattr(r, "player_name", None)
        canonical = _pn(wpba_data) or _pn(wpa_women_data) or _pn(wpa_men_data) or player_name
        result = {
            "player_name": canonical,
            "wpba": wpba,
            "wpa_women": wpa_women,
            "wpa_men": wpa_men,
            "tournament_stats": ts,
        }

        try:
            from api.services.ollama_narratives import generate_player_narrative
            from api.services.ollama_client import is_ollama_enabled
            from api.services.player_narrative_cache import (
                get_cached_narrative,
                hash_overview_payload,
                narrative_cache_key,
                remember_narrative,
            )

            _FALLBACK_NARRATIVE = "AI summary is temporarily unavailable."

            if is_ollama_enabled():
                pkey = narrative_cache_key(canonical)
                payload_hash = hash_overview_payload(result)
                cached_text = get_cached_narrative(pkey, payload_hash)
                if cached_text is not None:
                    result["narrative"] = cached_text
                    result["narrative_unchanged"] = True
                else:
                    narrative = await generate_player_narrative(result)
                    if narrative and narrative.strip():
                        result["narrative"] = narrative.strip()
                        result["narrative_unchanged"] = False
                        remember_narrative(pkey, payload_hash, narrative.strip())
                    else:
                        result["narrative"] = _FALLBACK_NARRATIVE
                        result["narrative_unchanged"] = False
        except Exception as narr_err:
            logger.warning("Narrative generation skipped: %s", narr_err)
            try:
                from api.services.ollama_client import is_ollama_enabled as _ioe

                if _ioe():
                    result["narrative"] = "AI summary is temporarily unavailable."
                    result["narrative_unchanged"] = False
            except Exception:
                pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching player overview: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


def _association_to_system(association: str) -> str:
    """Map frontend association to ranking_system (women/men only)."""
    m = {"WPBA": "WPBA_Women", "WPA": "WPA_Women", "WPA_Women": "WPA_Women", "WPA_Men": "WPA_Men"}
    return m.get(association, association)


@router.get("/{player_name}/history")
async def get_player_ranking_history(
    player_name: str,
    association: str = Query("WPBA", pattern="^(WPBA|WPA|WPBA_Women|WPA_Women|WPA_Men)$"),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """Get player's ranking history. Admin/super_admin: any; director/user: own only."""
    if not _can_access_player(current_user, player_name):
        raise HTTPException(status_code=403, detail="You can only view your own player performance.")
    try:
        engine = get_engine()
        resolved_name = _resolve_player_for_request(engine, player_name, current_user)
        ranking_system = _association_to_system(association)
        variants = _name_variants_for_lookup(resolved_name)
        if not variants:
            variants = [player_name.strip()]
        params = {f"v{i}": v for i, v in enumerate(variants)}
        params["ranking_system"] = ranking_system
        params["limit"] = limit
        where = _rankings_where_variants(variants)
        with engine.connect() as conn:
            history = conn.execute(
                text(f"""
                    SELECT 
                        rank,
                        points as rating,
                        snapshot_date as date,
                        ranking_system as association
                    FROM rankings
                    WHERE {where} AND ranking_system = :ranking_system
                    ORDER BY snapshot_date DESC
                    LIMIT :limit
                """),
                params,
            ).mappings().all()

        if not history:
            return {
                "player_name": player_name,
                "association": association,
                "history": []
            }
        
        return {
            "player_name": player_name,
            "association": association,
            "history": [dict(row) for row in history]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ranking history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{player_name}/tournaments")
async def get_player_tournaments(
    player_name: str,
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Get player's tournament results. Admin/super_admin: any; director/user: own only."""
    if not _can_access_player(current_user, player_name):
        raise HTTPException(status_code=403, detail="You can only view your own player performance.")
    try:
        engine = get_engine()
        resolved_name = _resolve_player_for_request(engine, player_name, current_user)
        with engine.connect() as conn:
            variants = _name_variants_for_lookup(resolved_name)
            if not variants:
                variants = [player_name.strip()]
            t_params = {f"v{i}": v for i, v in enumerate(variants)}
            t_params["limit"] = limit
            t_where = _rankings_where_variants(variants).replace("player_name", "tr.player_name")
            tournaments = conn.execute(
                text(f"""
                    SELECT 
                        th.tournament_id,
                        th.name as tournament_name,
                        th.association,
                        th.date as tournament_date,
                        th.location,
                        tr.placement,
                        tr.points,
                        tr.fargo_rating_at_scrape,
                        tr.notes
                    FROM tournament_results tr
                    JOIN tournament_history th ON tr.tournament_id = th.tournament_id
                    WHERE {t_where}
                    ORDER BY th.date DESC
                    LIMIT :limit
                """),
                t_params,
            ).mappings().all()
        
        return {
            "player_name": player_name,
            "tournaments": [dict(row) for row in tournaments],
            "total_count": len(tournaments)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching player tournaments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{player_name}/performance-metrics")
async def get_player_performance_metrics(player_name: str, current_user: dict = Depends(get_current_user)):
    """Get detailed performance metrics. Admin/super_admin: any; director/user: own only."""
    if not _can_access_player(current_user, player_name):
        raise HTTPException(status_code=403, detail="You can only view your own player performance.")
    try:
        engine = get_engine()
        resolved_name = _resolve_player_for_request(engine, player_name, current_user)
        with engine.connect() as conn:
            # Calculate win rate and performance trends
            pm_variants = _name_variants_for_lookup(resolved_name)
            if not pm_variants:
                pm_variants = [player_name.strip()]
            pm_params = {f"v{i}": v for i, v in enumerate(pm_variants)}
            pm_where = _rankings_where_variants(pm_variants)
            pm_where_tr = pm_where.replace("player_name", "tr.player_name")

            metrics = conn.execute(
                text(f"""
                    SELECT 
                        COUNT(*) as total_tournaments,
                        SUM(CASE WHEN placement = 1 THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN placement <= 3 THEN 1 ELSE 0 END) as top_3,
                        SUM(CASE WHEN placement <= 8 THEN 1 ELSE 0 END) as top_8,
                        AVG(placement) as avg_placement,
                        MIN(placement) as best_placement,
                        SUM(points) as total_points
                    FROM tournament_results
                    WHERE {pm_where}
                """),
                pm_params,
            ).mappings().first()

            # Get year-by-year breakdown
            yearly_stats = conn.execute(
                text(f"""
                    SELECT 
                        EXTRACT(YEAR FROM th.date) as year,
                        COUNT(*) as tournaments,
                        SUM(CASE WHEN tr.placement = 1 THEN 1 ELSE 0 END) as wins,
                        AVG(tr.placement) as avg_placement,
                        SUM(tr.points) as points
                    FROM tournament_results tr
                    JOIN tournament_history th ON tr.tournament_id = th.tournament_id
                    WHERE {pm_where_tr}
                    GROUP BY year
                    ORDER BY year DESC
                """),
                pm_params,
            ).mappings().all()
        
        return {
            "player_name": player_name,
            "overall_metrics": dict(metrics) if metrics else {},
            "yearly_breakdown": [dict(row) for row in yearly_stats]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _num(v: Any) -> Optional[float]:
    """JSON-serialize-friendly number from DB row."""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct(part: int, total: int) -> Optional[float]:
    if total <= 0:
        return None
    return round(100.0 * part / total, 1)


@router.get("/{player_name}/tournament-analytics")
async def get_tournament_analytics(
    player_name: str,
    window: str = Query("all_time", pattern="^(recent_3|season|all_time)$"),
    current_user: dict = Depends(get_current_user),
):
    """
    Placement and points aggregates for a time window (from tournament_results + tournament_history).
    All rates are empirical shares of events in the window (not model predictions).
    """
    if not _can_access_player(current_user, player_name):
        raise HTTPException(status_code=403, detail="You can only view your own player performance.")
    try:
        engine = get_engine()
        resolved_name = _resolve_player_for_request(engine, player_name, current_user)
        pm_variants = _name_variants_for_lookup(resolved_name)
        if not pm_variants:
            pm_variants = [player_name.strip()]
        pm_params: Dict[str, Any] = {f"v{i}": v for i, v in enumerate(pm_variants)}
        pm_where = _rankings_where_variants(pm_variants)
        pm_where_tr = pm_where.replace("player_name", "tr.player_name")
        pm_where_tr3 = pm_where.replace("player_name", "tr3.player_name")

        cal_year = datetime.now().year
        window_extra = ""
        if window == "season":
            window_extra = " AND EXTRACT(YEAR FROM th.date::timestamp) = :cal_year "
            pm_params["cal_year"] = cal_year
        elif window == "recent_3":
            window_extra = f"""
                AND tr.tournament_id IN (
                    SELECT tr3.tournament_id
                    FROM tournament_results tr3
                    JOIN tournament_history th3 ON tr3.tournament_id = th3.tournament_id
                    WHERE {pm_where_tr3} AND th3.date IS NOT NULL
                    GROUP BY tr3.tournament_id
                    ORDER BY MAX(th3.date) DESC NULLS LAST
                    LIMIT 3
                )
            """

        base_where = f"""
            {pm_where_tr}
            AND th.date IS NOT NULL
            {window_extra}
        """

        with engine.connect() as conn:
            agg = conn.execute(
                text(f"""
                    SELECT
                        COUNT(*) AS event_count,
                        SUM(CASE WHEN tr.placement = 1 THEN 1 ELSE 0 END) AS first_count,
                        SUM(CASE WHEN tr.placement <= 3 THEN 1 ELSE 0 END) AS top_3_count,
                        SUM(CASE WHEN tr.placement <= 8 THEN 1 ELSE 0 END) AS top_8_count,
                        AVG(tr.placement) AS avg_placement,
                        MIN(tr.placement) AS best_placement,
                        SUM(tr.points) AS total_points
                    FROM tournament_results tr
                    JOIN tournament_history th ON tr.tournament_id = th.tournament_id
                    WHERE {base_where}
                """),
                pm_params,
            ).mappings().first()

            events = conn.execute(
                text(f"""
                    SELECT
                        th.tournament_id,
                        th.name AS tournament_name,
                        th.date AS tournament_date,
                        th.association,
                        tr.placement,
                        tr.points
                    FROM tournament_results tr
                    JOIN tournament_history th ON tr.tournament_id = th.tournament_id
                    WHERE {base_where}
                    ORDER BY th.date DESC NULLS LAST
                    LIMIT 50
                """),
                pm_params,
            ).mappings().all()

            match_block: Optional[Dict[str, Any]] = None
            try:
                inspector = inspect(conn)
                if "tournament_history_matches" in inspector.get_table_names(schema="public"):
                    wn_conds = " OR ".join(
                        f"LOWER(TRIM(thm.winner_name)) = LOWER(TRIM(:v{i}))" for i in range(len(pm_variants))
                    )
                    p1_conds = " OR ".join(
                        f"LOWER(TRIM(thm.operator_name)) = LOWER(TRIM(:v{i}))" for i in range(len(pm_variants))
                    )
                    p2_conds = " OR ".join(
                        f"LOWER(TRIM(thm.player2_name)) = LOWER(TRIM(:v{i}))" for i in range(len(pm_variants))
                    )
                    participated = f"(({p1_conds}) OR ({p2_conds}))"
                    if window == "recent_3":
                        match_window_extra = f"""
                            AND th.tournament_id IN (
                                SELECT tr3.tournament_id
                                FROM tournament_results tr3
                                JOIN tournament_history th3 ON tr3.tournament_id = th3.tournament_id
                                WHERE {pm_where_tr3} AND th3.date IS NOT NULL
                                GROUP BY tr3.tournament_id
                                ORDER BY MAX(th3.date) DESC NULLS LAST
                                LIMIT 3
                            )
                        """
                    elif window == "season":
                        match_window_extra = " AND EXTRACT(YEAR FROM th.date::timestamp) = :cal_year "
                    else:
                        match_window_extra = ""

                    mrow = conn.execute(
                        text(f"""
                            SELECT
                                COUNT(*) AS match_decided,
                                SUM(CASE WHEN ({wn_conds}) THEN 1 ELSE 0 END) AS match_wins
                            FROM tournament_history_matches thm
                            JOIN tournament_history th ON thm.tournament_id = th.tournament_id
                            WHERE {participated}
                            AND thm.winner_name IS NOT NULL
                            AND TRIM(thm.winner_name) <> ''
                            AND th.date IS NOT NULL
                            {match_window_extra}
                        """),
                        pm_params,
                    ).mappings().first()

                    if mrow:
                        decided = int(mrow.get("match_decided") or 0)
                        wins = int(mrow.get("match_wins") or 0)
                        losses = max(0, decided - wins)
                        match_block = {
                            "matches_with_winner": decided,
                            "match_wins": wins,
                            "match_losses": losses,
                            "match_win_rate_pct": _pct(wins, decided),
                        }
            except Exception as me:
                logger.debug("Match-level analytics skipped: %s", me)

        ev = int(agg.get("event_count") or 0) if agg else 0
        first_c = int(agg.get("first_count") or 0) if agg else 0
        top3_c = int(agg.get("top_3_count") or 0) if agg else 0
        top8_c = int(agg.get("top_8_count") or 0) if agg else 0

        return {
            "player_name": player_name,
            "resolved_player_name": resolved_name,
            "window": window,
            "calendar_year": cal_year if window == "season" else None,
            "label": (
                "Last 3 events (by date)"
                if window == "recent_3"
                else f"Calendar year {cal_year}"
                if window == "season"
                else "All time"
            ),
            "counts": {
                "events": ev,
                "first_place": first_c,
                "top_3": top3_c,
                "top_8": top8_c,
            },
            "rates_pct": {
                "first_place": _pct(first_c, ev),
                "top_3": _pct(top3_c, ev),
                "top_8": _pct(top8_c, ev),
            },
            "avg_placement": _num(agg.get("avg_placement") if agg else None),
            "best_placement": int(agg["best_placement"])
            if ev > 0 and agg is not None and agg.get("best_placement") is not None
            else None,
            "total_points": _num(agg.get("total_points") if agg else None),
            "match_record": match_block,
            "events": [dict(row) for row in events],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching tournament analytics: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{player_name}/historical-ratings")
async def get_player_historical_ratings(
    player_name: str,
    limit: int = Query(100, ge=1, le=500),
    rating_type: Optional[str] = Query(None, regex="^(fargo|alfa|est)?$"),
    current_user: dict = Depends(get_current_user),
):
    """
    Get player's historical rating data across all rating types.

    Args:
        player_name: Name of the player
        limit: Maximum number of historical records (1-500)
        rating_type: Optional filter for specific rating type
    """
    # Input validation
    if not player_name or not isinstance(player_name, str) or len(player_name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Valid player name is required")

    if not _can_access_player(current_user, player_name):
        raise HTTPException(status_code=403, detail="You can only view your own player performance.")

    try:
        from api.services.rating_archive_service import RatingArchiveService
        db = get_database_manager()
        archive_service = RatingArchiveService(db)

        # Resolve canonical name for lookups (license-first, then aliases, then variants)
        engine = get_engine()
        canonical_name = _resolve_player_for_request(engine, player_name, current_user) or player_name.strip()

        # Get player ID first
        conn = None
        try:
            conn = db.get_connection()
            cursor = conn.cursor()

            # Validate database connection
            if not conn or conn.closed:
                raise HTTPException(status_code=500, detail="Database connection unavailable")

            # Case-insensitive lookup: try "First Last" and "Last, First" variants
            variants = _name_variants_for_lookup(canonical_name)
            if not variants:
                variants = [canonical_name.strip()]
            player_row = None
            for v in variants:
                cursor.execute(
                    """
                    SELECT player_id, first_name, last_name FROM players
                    WHERE LOWER(TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,''))) = LOWER(TRIM(%s))
                       OR (first_name IS NOT NULL AND last_name IS NOT NULL
                           AND LOWER(TRIM(last_name || ', ' || first_name)) = LOWER(TRIM(%s)))
                    LIMIT 1
                    """,
                    (v, v),
                )
                player_row = cursor.fetchone()
                if player_row:
                    break

            if not player_row:
                raise HTTPException(status_code=404, detail=f"Player {player_name} not found")

            player_id = player_row[0]
            first_name = (player_row[1] or "").strip()
            last_name = (player_row[2] or "").strip()
            name_variants = [player_name.strip(), canonical_name]
            if first_name and last_name:
                name_variants.append(f"{last_name}, {first_name}")
            name_variants = list(dict.fromkeys(n for n in name_variants if n))

        finally:
            if conn:
                try:
                    conn.close()
                except Exception as close_error:
                    logger.warning(f"Error closing database connection: {close_error}")

        # Get historical rating data (fargo_rating_history, alfa_rating_history, est_rating_transitions)
        historical_data = archive_service.get_player_rating_history(player_id, rating_type, limit)

        # Group by rating type and sort by date
        rating_series = {
            'fargo': [],
            'alfa': [],
            'est': []
        }

        for entry in historical_data:
            try:
                rating_series[entry['rating_type']].append({
                    'date': entry['snapshot_date'],
                    'rating': entry['rating_value'],
                    'confidence': entry['confidence_score'],
                    'source': entry['source']
                })
            except KeyError as e:
                logger.warning(f"Missing key in historical data entry: {e}")
                continue

        # Enrich Fargo from rankings snapshots (scraped archives): one point per snapshot_date
        fargo_by_date: Dict[str, Dict[str, Any]] = {e['date']: e for e in rating_series['fargo'] if e.get('date')}
        try:
            conn = db.get_connection()
            cur = conn.cursor()
            # Match rankings by display name or "Last, First" (common in scraped data)
            placeholders = ",".join(["%s"] * len(name_variants))
            cur.execute(
                f"""
                SELECT DISTINCT ON (snapshot_date) snapshot_date, fargo_rating
                FROM rankings
                WHERE player_name IN ({placeholders}) AND fargo_rating IS NOT NULL
                ORDER BY snapshot_date DESC
                LIMIT %s
                """,
                (*name_variants, limit),
            )
            for row in cur.fetchall():
                snap_date = row[0]
                date_str = snap_date.isoformat() if hasattr(snap_date, 'isoformat') else str(snap_date)
                if date_str not in fargo_by_date:
                    fargo_by_date[date_str] = {
                        'date': date_str,
                        'rating': float(row[1]),
                        'confidence': 0.7,
                        'source': 'rankings_snapshot',
                    }
            conn.close()
        except Exception as e:
            logger.warning("Could not enrich Fargo from rankings snapshots: %s", e)

        rating_series['fargo'] = sorted(fargo_by_date.values(), key=lambda x: x['date'] or '')

        # Sort alfa and est by date
        for rt in ('alfa', 'est'):
            rating_series[rt].sort(key=lambda x: x['date'] if x['date'] else '')

        total_entries = sum(len(rating_series[rt]) for rt in rating_series)
        logger.info(f"Retrieved historical ratings for {player_name} (Fargo enriched from archives + rankings snapshots)")
        return {
            "success": True,
            "player_name": player_name,
            "player_id": player_id,
            "rating_series": rating_series,
            "total_entries": total_entries,
            "filtered_by_type": rating_type
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching historical ratings for {player_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)[:100]}")


@router.get("/{player_name}/tournament-statistics")
async def get_player_tournament_statistics(
    player_name: str,
    current_user: dict = Depends(get_current_user),
):
    """Get comprehensive tournament statistics for a player."""
    if not _can_access_player(current_user, player_name):
        raise HTTPException(status_code=403, detail="You can only view your own player performance.")

    try:
        # Resolve canonical name (license-first, then aliases, then variants)
        engine = get_engine()
        canonical = _resolve_player_for_request(engine, player_name, current_user) or player_name
        from api.routes.tournament_history import get_player_tournament_history
        tournament_data = await get_player_tournament_history(canonical)

        # Calculate additional statistics
        results = tournament_data.get('tournament_results', [])
        stats = tournament_data.get('statistics', {})

        # Performance over time analysis
        performance_trend = []
        yearly_stats = {}

        for result in results:
            year = result.get('year')
            if year:
                if year not in yearly_stats:
                    yearly_stats[year] = {
                        'tournaments': 0,
                        'wins': 0,
                        'top3': 0,
                        'avg_placement': [],
                        'total_points': 0
                    }

                yearly_stats[year]['tournaments'] += 1
                placement = result.get('placement')
                points = result.get('points', 0)

                if placement == 1:
                    yearly_stats[year]['wins'] += 1
                if placement and placement <= 3:
                    yearly_stats[year]['top3'] += 1
                if placement:
                    yearly_stats[year]['avg_placement'].append(placement)
                yearly_stats[year]['total_points'] += points or 0

        # Calculate averages
        for year_data in yearly_stats.values():
            if year_data['avg_placement']:
                year_data['avg_placement'] = sum(year_data['avg_placement']) / len(year_data['avg_placement'])
            else:
                year_data['avg_placement'] = None

        return {
            "success": True,
            "player_name": player_name,
            "basic_stats": stats,
            "yearly_breakdown": yearly_stats,
            "recent_tournaments": results[:10],  # Last 10 tournaments
            "performance_trend": sorted([
                {
                    'year': year,
                    'avg_placement': data['avg_placement'],
                    'win_rate': data['wins'] / data['tournaments'] if data['tournaments'] > 0 else 0,
                    'top3_rate': data['top3'] / data['tournaments'] if data['tournaments'] > 0 else 0
                }
                for year, data in yearly_stats.items()
            ], key=lambda x: x['year'])
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching tournament statistics for {player_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
