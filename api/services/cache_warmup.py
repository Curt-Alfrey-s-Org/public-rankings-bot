"""
Cache warmup for startup and scheduled refresh.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)


def run_cache_warmup_impl() -> Dict[str, Any]:
    """
    Refresh materialized views and pre-warm caches.

    Returns:
        Dict with warmup summary stats.
    """
    if os.getenv("SKIP_CACHE_WARMUP", "").lower() in ("1", "true", "yes"):
        logger.info("[CACHE] Warmup skipped via SKIP_CACHE_WARMUP")
        return {"skipped": True}

    summary: Dict[str, Any] = {"skipped": False}

    try:
        from database import get_database_manager

        db_manager = get_database_manager()
        summary["materialized_views"] = db_manager.refresh_materialized_views()
    except Exception as exc:
        logger.warning("[CACHE] Materialized view refresh failed: %s", exc)
        summary["materialized_views"] = {"status": "failed", "error": str(exc)}

    # Rankings cache warmup disabled - function not implemented
    # try:
    #     from api.routes.rankings import build_rankings_cache_payloads
    #     summary["rankings"] = build_rankings_cache_payloads()
    # except Exception as exc:
    #     logger.warning("[CACHE] Rankings warmup failed: %s", exc)
    #     summary["rankings"] = {"status": "failed", "error": str(exc)}
    summary["rankings"] = {"status": "disabled", "note": "build_rankings_cache_payloads not implemented"}

    try:
        from api.routes.tournament_history import build_tournament_cache_payloads

        summary["tournaments"] = build_tournament_cache_payloads()
    except Exception as exc:
        logger.warning("[CACHE] Tournament warmup failed: %s", exc)
        summary["tournaments"] = {"status": "failed", "error": str(exc)}

    return summary
