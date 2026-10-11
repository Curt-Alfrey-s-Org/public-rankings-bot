"""
Health check service: Database, Redis, API probes.
Provides unified health status for monitoring dashboards.
"""

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Build hash baked into the image at build time (see Dockerfile ARG BUILD_HASH).
# Read once at import so every health response includes it.
_BUILD_HASH_FILE = Path("/app/.build-hash")
try:
    _BUILD_HASH = _BUILD_HASH_FILE.read_text().strip() if _BUILD_HASH_FILE.exists() else "unknown"
except Exception:
    _BUILD_HASH = "unknown"


def get_build_hash() -> str:
    """Same value as reported on GET /api/health (image build fingerprint)."""
    return _BUILD_HASH


# Module-level startup time (set by bot's lifespan)
_startup_time: Optional[float] = None


def set_startup_time(t: float) -> None:
    """Set process startup timestamp for uptime calculation."""
    global _startup_time
    _startup_time = t


def get_uptime_seconds() -> Optional[float]:
    """Return uptime in seconds since startup."""
    if _startup_time is None:
        return None
    return time.time() - _startup_time


def check_database(engine=None, session_factory=None) -> Dict[str, Any]:
    """
    Probe database connectivity and measure latency.
    Pass either engine (SQLAlchemy) or session_factory.
    """
    result: Dict[str, Any] = {
        "status": "unknown",
        "latency_ms": None,
        "error": None,
    }
    try:
        from sqlalchemy import text

        start = time.perf_counter()
        if engine is not None:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        elif session_factory is not None:
            session = session_factory()
            try:
                session.execute(text("SELECT 1"))
            finally:
                session.close()
        else:
            result["error"] = "No database configured"
            result["status"] = "skipped"
            return result
        elapsed_ms = (time.perf_counter() - start) * 1000
        result["latency_ms"] = round(elapsed_ms, 2)
        result["status"] = "healthy" if elapsed_ms < 5000 else "degraded"
    except Exception as e:
        result["status"] = "unhealthy"
        result["error"] = str(e)[:200]
        logger.warning("Database health check failed: %s", e)
    return result


def check_rankings_db(engine=None) -> Dict[str, Any]:
    """
    Check the rankings DB (Postgres) used by DatabaseManager.
    Returns status healthy if we can run SELECT 1; otherwise unhealthy/skipped.
    """
    result: Dict[str, Any] = {
        "status": "unknown",
        "latency_ms": None,
        "error": None,
    }
    if not engine:
        result["status"] = "skipped"
        result["error"] = "Rankings DB engine not configured"
        return result
    try:
        from sqlalchemy import text
        start = time.perf_counter()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        elapsed_ms = (time.perf_counter() - start) * 1000
        result["latency_ms"] = round(elapsed_ms, 2)
        result["status"] = "healthy" if elapsed_ms < 5000 else "degraded"
    except Exception as e:
        result["status"] = "unhealthy"
        result["error"] = str(e)[:200]
        logger.warning("Rankings DB health check failed: %s", e)
    return result


def check_redis() -> Dict[str, Any]:
    """
    Probe Redis if REDIS_URL is configured.
    """
    import os

    redis_url = os.getenv("REDIS_URL", "").strip()
    result: Dict[str, Any] = {
        "configured": bool(redis_url),
        "status": "unknown",
        "latency_ms": None,
        "error": None,
    }
    if not redis_url:
        result["status"] = "not_configured"
        return result
    try:
        import redis

        r = redis.from_url(redis_url)
        start = time.perf_counter()
        r.ping()
        elapsed_ms = (time.perf_counter() - start) * 1000
        result["latency_ms"] = round(elapsed_ms, 2)
        result["status"] = "healthy"
    except ImportError:
        result["status"] = "not_available"
        result["error"] = "redis package not installed"
    except Exception as e:
        result["status"] = "unhealthy"
        result["error"] = str(e)[:200]
        logger.warning("Redis health check failed: %s", e)
    return result


def get_error_log_tail(log_path: Optional[Path], lines: int = 20) -> list:
    """Return last N lines containing ERROR from log file."""
    if not log_path or not log_path.exists():
        return []
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
        error_lines = [ln.strip() for ln in all_lines if "ERROR" in ln.upper() or "CRITICAL" in ln.upper()]
        return error_lines[-lines:]
    except Exception as e:
        logger.warning("Could not read log file %s: %s", log_path, e)
        return []


def check_ollama() -> Dict[str, Any]:
    """Probe Ollama connectivity via sync HTTP (safe to call from async context)."""
    import os

    try:
        from api.services.ollama_client import is_ollama_enabled, get_ollama_base_url

        if not is_ollama_enabled():
            return {"status": "not_configured", "enabled": False}

        base_url = get_ollama_base_url()
        import httpx
        start = time.perf_counter()
        resp = httpx.get(f"{base_url}/", timeout=5.0)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        model_structured = os.getenv("OLLAMA_MODEL_STRUCTURED", "mistral:7b")
        model_chat = os.getenv("OLLAMA_MODEL_CHAT", "llama3.1:8b")

        return {
            "status": "healthy" if resp.status_code == 200 else "degraded",
            "latency_ms": latency_ms,
            "base_url": base_url,
            "enabled": True,
            "models": {"structured": model_structured, "chat": model_chat},
        }
    except Exception as e:
        logger.warning("Ollama health check failed: %s", e)
        return {"status": "unreachable", "enabled": True, "error": str(e)[:200]}


def run_health_checks(
    service_name: str,
    version: str = "1.0.0",
    engine=None,
    session_factory=None,
    log_path: Optional[Path] = None,
    rankings_db_path=None,
) -> Dict[str, Any]:
    """
    Run all health probes and return aggregated status.
    rankings_db_path is ignored; rankings DB is checked via engine (Postgres).
    """
    db_result = check_database(engine=engine, session_factory=session_factory)
    rankings_db_result = check_rankings_db(engine)
    redis_result = check_redis()
    ollama_result = check_ollama()
    try:
        from scrapers.fetch_utils import get_scraper_health_metrics
        scraper_metrics = get_scraper_health_metrics()
    except Exception:
        scraper_metrics = {"status": "unavailable"}
    try:
        from api.services.background_supervisor import get_background_task_health
        background_tasks = get_background_task_health()
    except Exception:
        background_tasks = {}
    uptime = get_uptime_seconds()

    overall = "healthy"
    # Required: auth DB or rankings DB failing -> unhealthy
    if db_result.get("status") == "unhealthy" or rankings_db_result.get("status") == "unhealthy":
        overall = "unhealthy"
    elif (
        db_result.get("status") == "degraded"
        or rankings_db_result.get("status") == "degraded"
        or redis_result.get("status") == "unhealthy"
        or redis_result.get("status") == "degraded"
    ):
        overall = "degraded"
    if any(bool(task.get("degraded")) for task in background_tasks.values()):
        overall = "degraded"

    return {
        "status": overall,
        "service": service_name,
        "version": version,
        "build_hash": _BUILD_HASH,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(uptime, 1) if uptime is not None else None,
        "database": db_result,
        "rankings_db": rankings_db_result,
        "redis": redis_result,
        "ollama": ollama_result,
        "scrapers": scraper_metrics,
        "background_tasks": background_tasks,
        "error_logs": get_error_log_tail(log_path) if log_path else [],
    }


def get_basic_health(service_name: str, version: str = "1.0.0") -> Dict[str, Any]:
    """Minimal health response for fast probes (no DB/Redis checks)."""
    uptime = get_uptime_seconds()
    return {
        "status": "healthy",
        "service": service_name,
        "version": version,
        "build_hash": _BUILD_HASH,
        "uptime_seconds": round(uptime, 1) if uptime is not None else None,
    }
