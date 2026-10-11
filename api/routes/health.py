"""
Health check API routes. Postgres only (engine for rankings DB).
GET /api/health - Basic probe (fast); never returns 5xx so probes always get 200.
GET /api/health/detailed - Full status with DB, Redis, uptime, error logs
"""

import logging
from pathlib import Path

from fastapi import APIRouter

from api.services.health_check import (
    get_basic_health,
    run_health_checks,
)

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SERVICE_NAME = "Rankings Bot API"
VERSION = "1.0.0"


def _get_log_path() -> Path:
    return PROJECT_ROOT / "rankings_bot.log"


@router.get("/health")
async def health_basic():
    """Basic health probe for load balancers and uptime monitors. Never returns 5xx."""
    try:
        return get_basic_health(SERVICE_NAME, VERSION)
    except Exception as e:
        logger.warning("Health basic failed, returning degraded: %s", e)
        return {
            "status": "degraded",
            "service": SERVICE_NAME,
            "version": VERSION,
            "uptime_seconds": None,
            "error": "health check failed",
        }


@router.get("/health/detailed")
async def health_detailed():
    """Detailed health: auth DB, rankings DB (Postgres), Redis, uptime, error logs."""
    try:
        from database import get_engine
        engine = get_engine()
        return run_health_checks(
            service_name=SERVICE_NAME,
            version=VERSION,
            engine=engine,
            session_factory=None,
            log_path=_get_log_path(),
        )
    except Exception as e:
        logger.warning("Health detailed failed: %s", e)
        return {
            "status": "unhealthy",
            "service": SERVICE_NAME,
            "version": VERSION,
            "error": str(e)[:200],
        }
