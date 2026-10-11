"""
FastAPI Application - Main Entry Point
Provides REST API endpoints for React frontend to display rankings data
"""

# Doc refs (AI / maintainers): docs/AUTH_DOC_HOOKS.md; docs/AUTH_DESIGN.md;
#   docs/SECURITY_ANALYSIS.md (JWT/CORS); docs/PRODUCTION_DEPLOYMENT.md (routers, static)

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
import asyncio
import logging
import os
import sys
import jwt
from datetime import date

# Import performance utilities
from api.utils.performance import get_timestamp
from project_root import PROJECT_ROOT

# Import error handling utilities
from api.middleware.exception_handler import ExceptionHandlerMiddleware
from api.middleware.error_sanitizer import ErrorSanitizerMiddleware
from api.middleware.request_id import RequestIdMiddleware
from api.middleware.access_control import RequireApiKeyMiddleware, RequireUserOrAdminMiddleware
from api.services.background_supervisor import start_supervised_task
from api.services.health_check import get_build_hash

# Initialize DEBUG_MODE
DEBUG_MODE = os.getenv('DEBUG', 'false').lower() == 'true'

# API key auth (enforced by RequireApiKeyMiddleware; policy in docs/API_ACCESS_POLICY.md)
API_KEY_HEADER = "X-API-Key"
BOT_API_KEY = os.getenv("BOT_API_KEY", "").strip()

# Conditionally import LoggingMiddleware
LoggingMiddleware: Optional[type] = None
if DEBUG_MODE:
    try:
        from api.middleware.logging import LoggingMiddleware as _LoggingMiddleware
        LoggingMiddleware = _LoggingMiddleware
    except ImportError as e:
        logger = logging.getLogger(__name__)
        logger.warning("DEBUG logging middleware unavailable: %s", e)

# Add parent directory to path to import bot modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import auth as auth_lib
from api.routes import auth, auth_v1, splash_v1, rankings, system, logs, docs, settings, network, tournaments, tournament_wizard, tournament_history, player_performance, users, ai_coach, rankings_assistant, payments, coupons, notifications, fargo, head_to_head, ai_narrative, email_test, health, news, messages, assets, media, admin, admin_dev_tools, covert_ops, events, appearance, director, alfa, login_features, splash_config, leagues, tours, alfa_ratings, ui_customizations, profile, admin_security, backups, live_updates, csv_import, rules, test_tournaments, test_center_views, rating_accuracy, self_calibration, metrics, data_quality
from api.routes.users import list_users, create_user, UserListResponse, CreateUserRequest
from database import get_engine, get_session_local, Base
engine = get_engine()
from api.models.user import User
from api.models.auth_token import EmailVerificationToken
from api.models.audit import AuditLog
from sqlalchemy.orm import Session


def configure_logging() -> None:
    """Configure logging with file handler and appropriate log level."""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    if DEBUG_MODE:
        log_level = 'DEBUG'

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    try:
        log_file = Path(os.environ.get("LOG_FILE", "")).resolve() if os.environ.get("LOG_FILE") else PROJECT_ROOT / "rankings_bot.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, log_level, logging.INFO))
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        )
        logging.getLogger().addHandler(file_handler)
    except Exception as e:
        print(f"Could not add rankings_bot.log handler: {e}", file=sys.stderr)


def discover_rebuild_script() -> None:
    """Auto-discover rebuild_website_now.sh and set REBUILD_WEBSITE_SCRIPT env var."""
    if os.environ.get("REBUILD_WEBSITE_SCRIPT"):
        return

    rebuild_script = None

    # Check PROJECT_ROOT/scripts/rebuild_website_now.sh
    script_path = PROJECT_ROOT / "scripts" / "rebuild_website_now.sh"
    if script_path.is_file():
        rebuild_script = script_path

    # Check current working directory
    if rebuild_script is None:
        try:
            cwd_script = Path(os.getcwd()).resolve() / "scripts" / "rebuild_website_now.sh"
            if cwd_script.is_file():
                rebuild_script = cwd_script
        except OSError as e:
            logger.warning("Could not inspect cwd for rebuild script: %s", e)

    if rebuild_script is not None:
        os.environ["REBUILD_WEBSITE_SCRIPT"] = str(rebuild_script)
        logger.info("REBUILD_WEBSITE_SCRIPT set automatically to %s", rebuild_script)


def discover_rebuild_all_script() -> None:
    """Auto-discover full_deploy.sh and set REBUILD_ALL_IMAGES_SCRIPT env var."""
    if os.environ.get("REBUILD_ALL_IMAGES_SCRIPT"):
        return

    script_path = PROJECT_ROOT / "scripts" / "full_deploy.sh"
    if script_path.is_file():
        os.environ["REBUILD_ALL_IMAGES_SCRIPT"] = str(script_path)
        logger.info("REBUILD_ALL_IMAGES_SCRIPT set automatically to %s", script_path)


# Initialize logging and discover rebuild script
configure_logging()
logger = logging.getLogger(__name__)
logger.info(f"Logging configured - Level: {os.getenv('LOG_LEVEL', 'INFO').upper()}, Debug Mode: {DEBUG_MODE}")

discover_rebuild_script()
discover_rebuild_all_script()


# Database setup
def get_db():
    """FastAPI dependency for database session."""
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()



def _validate_production_security():
    """Validate production security requirements during startup."""
    # Production readiness: fail startup if JWT_SECRET is unset or default (security: prevents token forgery)
    _jwt_secret = os.environ.get("JWT_SECRET", "")
    _is_production = os.environ.get("DEBUG", "false").lower() not in ("1", "true", "yes")
    _jwt_placeholders = ("rankings-bot-change-in-production", "change-this-in-production")
    if _is_production and (not _jwt_secret or _jwt_secret.strip() in _jwt_placeholders):
        logger.error(
            "[STARTUP] JWT_SECRET must be set to a strong random value in production. "
            "Set JWT_SECRET in .env (e.g. openssl rand -hex 32). See docs/SECURITY_ANALYSIS.md."
        )
        raise RuntimeError(
            "JWT_SECRET is unset or default. Set a strong unique value for production. "
            "Use: openssl rand -hex 32"
        )
    if not _is_production and (not _jwt_secret or _jwt_secret.strip() in _jwt_placeholders):
        logger.warning(
            "[STARTUP] JWT_SECRET is unset or default (ok for dev). Set for production. See docs/SECURITY_ANALYSIS.md."
        )
    # BOT_API_KEY gates anonymous non-public /api/* requests (RequireApiKeyMiddleware).
    if _is_production and not BOT_API_KEY:
        logger.error("[STARTUP] BOT_API_KEY must be set in production. See docs/API_ACCESS_POLICY.md.")
        raise RuntimeError(
            "BOT_API_KEY is unset. Set a strong unique value for production (e.g. openssl rand -hex 32)."
        )


def _initialize_database_tables():
    """Initialize database tables and verify PostgreSQL setup."""
    # Create database tables (auth/ORM)
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("[STARTUP] Database tables created/verified")
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            logger.info("[STARTUP] Database tables/indexes already exist (ok)")
        else:
            raise

    # When using Postgres, ensure rankings tables exist (schema_postgres.sql)
    try:
        from database import ensure_rankings_tables_postgres
        ensure_rankings_tables_postgres()
    except Exception as e:
        logger.warning("[STARTUP] ensure_rankings_tables_postgres: %s", e)


def _bootstrap_auth_users() -> dict:
    """Create missing bootstrap users from env credentials (api.auth.ensure_bootstrap_users).

    Raises on failure (api.auth.BootstrapConfigError for missing/invalid credentials,
    or the underlying DB error) so the self-test reports the real outcome.
    """
    from api.auth import ensure_bootstrap_users
    db = get_session_local()()
    try:
        summary = ensure_bootstrap_users(db)
    finally:
        db.close()
    logger.info(
        "[STARTUP] Auth bootstrap completed: created=%s existing=%s skipped=%s",
        summary.get("created"), summary.get("existing"), summary.get("skipped"),
    )
    return summary


# Set by _run_startup_self_tests when bootstrap credentials are missing/invalid; lifespan aborts
# startup in production (fail loudly instead of running without a usable super admin).
_auth_bootstrap_config_error: Optional[Exception] = None


def _run_startup_self_tests():
    """Run startup self-tests and return test results."""
    global _auth_bootstrap_config_error
    test_results = []
    passed = 0
    failed = 0

    # Test 1: Auth bootstrap (reports the real result; failures are no longer swallowed)
    _auth_bootstrap_config_error = None
    try:
        _bootstrap_auth_users()
        test_results.append({"name": "Auth Bootstrap", "passed": True, "duration_ms": 0})
        passed += 1
        logger.info("[SELFTEST] ✓ Auth Bootstrap")
    except Exception as e:
        if isinstance(e, auth_lib.BootstrapConfigError):
            _auth_bootstrap_config_error = e
        test_results.append({"name": "Auth Bootstrap", "passed": False, "duration_ms": 0, "error": str(e)})
        failed += 1
        logger.error("[SELFTEST] ✗ Auth Bootstrap: %s", e)

    # Test 2: Route Registration
    try:
        route_paths = [route.path for route in app.routes]
        expected_routes = ['/api/health', '/api/rankings', '/api/system']
        found_routes = [path for path in expected_routes if any(path in rp for rp in route_paths)]
        if len(found_routes) >= 2:
            test_results.append({"name": "Route Registration", "passed": True, "duration_ms": 0})
            passed += 1
            logger.info("[SELFTEST] ✓ Route Registration")
        else:
            raise Exception(f"Only {len(found_routes)}/{len(expected_routes)} routes found")
    except Exception as e:
        test_results.append({"name": "Route Registration", "passed": False, "duration_ms": 0, "error": str(e)})
        failed += 1
        logger.info("[SELFTEST] ✗ Route Registration: %s", e)

    # Test 3: CORS Configuration
    try:
        has_cors = any('CORSMiddleware' in str(middleware) for middleware in app.user_middleware)
        if has_cors:
            test_results.append({"name": "CORS Configuration", "passed": True, "duration_ms": 0})
            passed += 1
            logger.info("[SELFTEST] ✓ CORS Configuration")
        else:
            raise Exception("CORS middleware not found")
    except Exception as e:
        test_results.append({"name": "CORS Configuration", "passed": False, "duration_ms": 0, "error": str(e)})
        failed += 1
        logger.info("[SELFTEST] ✗ CORS Configuration: %s", e)

    # Test 4: Database Check
    try:
        from database import get_database_manager, ensure_rankings_tables_postgres
        db = get_database_manager()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        ensure_rankings_tables_postgres()  # ensure auth_sessions and other tables exist
        test_results.append({"name": "Database Check", "passed": True, "duration_ms": 0})
        passed += 1
        logger.info("[SELFTEST] ✓ Database Check")
    except Exception as e:
        test_results.append({"name": "Database Check", "passed": False, "duration_ms": 0, "error": str(e)[:80]})
        failed += 1
        logger.info("[SELFTEST] ✗ Database Check: %s", e)

    return test_results, passed, failed


async def _startup_recovery_tasks():
    """Run data freshness checks and recovery tasks."""
    try:
        from database import get_database_manager
        from datetime import date
        db_manager = get_database_manager()
        systems_to_check = ['WPBA_Women', 'WPA_Women']
        startup_status = {}
        needs_auto_refresh = False
        logger.info("[STARTUP-RECOVERY] Starting data freshness checks...")
        for ranking_system in systems_to_check:
            try:
                last_snapshot_date = db_manager.get_last_snapshot_date(ranking_system)
                if last_snapshot_date is None:
                    startup_status[ranking_system] = {"last_update": None, "age_days": None, "stale": True, "reason": "missing"}
                    needs_auto_refresh = True
                    logger.warning(f"[STARTUP-RECOVERY] {ranking_system}: NO DATA (run a manual refresh or cron when ready)")
                else:
                    # Handle both date objects and string dates for backward compatibility
                    if isinstance(last_snapshot_date, str):
                        from datetime import datetime
                        last_snapshot_date = datetime.fromisoformat(last_snapshot_date).date()
                    age_days = (date.today() - last_snapshot_date).days
                    is_stale = age_days > 1
                    startup_status[ranking_system] = {"last_update": last_snapshot_date.isoformat(), "age_days": age_days, "stale": is_stale, "reason": "stale" if is_stale else "fresh"}
                    if is_stale:
                        needs_auto_refresh = True
                        logger.warning(f"[STARTUP-RECOVERY] {ranking_system}: STALE ({age_days}d) — no automatic scrape; refresh manually or via scheduled script")
                    else:
                        logger.info(f"[STARTUP-RECOVERY] {ranking_system}: FRESH ({age_days}d)")
            except Exception as e:
                logger.error(f"[STARTUP-RECOVERY] Error checking {ranking_system}: {e}")
                startup_status[ranking_system] = {"last_update": None, "age_days": None, "stale": True, "reason": "check_failed", "error": str(e)}
                needs_auto_refresh = True
        logger.info(
            "[STARTUP-RECOVERY] Startup check complete. Stale/missing data: %s (not auto-refreshed by the API).",
            "yes" if needs_auto_refresh else "no",
        )
        return {"needs_refresh": needs_auto_refresh, "systems": startup_status}
    except Exception as e:
        logger.error(f"[STARTUP-RECOVERY] Error: {e}", exc_info=True)
        return {"needs_refresh": False, "error": str(e)}


async def _run_background_startup_tasks():
    """Run heavy startup tasks in background."""
    try:
        from api.lifespan_startup import run_self_tests_and_enrichment_impl
        await asyncio.get_running_loop().run_in_executor(None, run_self_tests_and_enrichment_impl, app)
    except Exception as e:
        logger.error("[STARTUP] Background self-tests/enrichment failed: %s", e)

    try:
        await _startup_recovery_tasks()
    except Exception as e:
        logger.error("[STARTUP] Background recovery failed: %s", e)

    try:
        from api.services.background_scheduler import start_background_scheduler
        start_background_scheduler()
        logger.info("[STARTUP] Background scheduler started (no auto-scrapers)")
    except Exception as e:
        logger.warning("[STARTUP] Background scheduler failed to start: %s", e)

    try:
        from api.services.cache_warmup import run_cache_warmup_impl
        await asyncio.get_running_loop().run_in_executor(None, run_cache_warmup_impl)
        logger.info("[STARTUP] Cache warmup completed")
    except Exception as e:
        logger.warning("[STARTUP] Cache warmup failed: %s", e)

    logger.info("[STARTUP] Background startup (self-tests, enrichment, recovery) completed.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    background_startup_task = None
    """Lifespan: minimal sync init, then yield; self-tests, enrichment, recovery run in background."""
    import time

    startup_start = time.time()
    startup_ts = get_timestamp()

    try:
        from api.services.health_check import set_startup_time
        set_startup_time(startup_start)
    except ImportError as e:
        logger.warning("Health check startup hook unavailable: %s", e)

    logger.info(f"[STARTUP] {startup_ts} API startup began")

    # Validate production security requirements
    _validate_production_security()

    # Minimal sync init only; heavy work runs in background so app accepts requests quickly
    _phase_start = time.time()
    test_start = time.time()

    try:
        # Initialize database tables
        _initialize_database_tables()

        # Run startup self-tests
        test_results, passed, failed = _run_startup_self_tests()

        test_elapsed = time.time() - test_start
        total = passed + failed
        all_passed = failed == 0
        if all_passed:
            logger.info(f"[SELFTEST] ✓ Startup self-tests passed: {passed}/{total} in {test_elapsed:.3f}s")
        else:
            logger.info(f"[SELFTEST] ⚠ Startup self-tests: {passed}/{total} passed, {failed} failed in {test_elapsed:.3f}s")
            for test_result in test_results:
                if not test_result["passed"]:
                    duration = test_result.get('duration_ms', 0)
                    error = test_result.get('error', 'Unknown error')
                    logger.info(f"[SELFTEST] ✗ {test_result['name']} ({duration:.0f}ms): {error}")

        if _auth_bootstrap_config_error is not None and auth_lib.is_production():
            raise RuntimeError(
                f"Startup aborted: {_auth_bootstrap_config_error}"
            ) from _auth_bootstrap_config_error

    except Exception as e:
        logger.error(f"[STARTUP] Minimal init failed: {e}", exc_info=True)
        raise

    _minimal_elapsed = time.time() - _phase_start
    logger.info(f"[STARTUP] Minimal init done in {_minimal_elapsed:.2f}s; app accepting requests. Self-tests, enrichment, recovery running in background.")

    # Defer heavy startup to background so /api/health and requests are served in seconds
    from api.services.live_updates import set_main_event_loop
    _loop = asyncio.get_running_loop()
    set_main_event_loop(_loop)

    background_startup_task = start_supervised_task(
        "startup_tasks",
        _run_background_startup_tasks,
        crash_threshold=3,
        crash_window_sec=300,
        base_backoff_sec=1.0,
        max_backoff_sec=30.0,
    )
    yield  # Application runs here — heavy startup continues in background

    if background_startup_task is not None and not background_startup_task.done():
        background_startup_task.cancel()
        try:
            await background_startup_task
        except asyncio.CancelledError:
            logger.info("[SHUTDOWN] Background startup supervisor cancelled")

    # Shutdown: stop background scheduler
    shutdown_ts = get_timestamp()
    logger.info(f"[SHUTDOWN] {shutdown_ts} API shutdown began")
    try:
        from api.services.background_scheduler import stop_background_scheduler
        stop_background_scheduler()
        logger.info("[SHUTDOWN] Background scheduler stopped")
    except Exception as e:
        logger.warning("[SHUTDOWN] Background scheduler stop: %s", e)

    # Shutdown: cleanup FairMatch Chrome driver (prevents orphaned Chrome processes)
    try:
        from api.services.fairmatch_scraper import cleanup_persistent_driver
        cleanup_persistent_driver()
        logger.info("[SHUTDOWN] FairMatch Chrome driver cleaned up")
    except Exception as e:
        logger.warning("[SHUTDOWN] FairMatch driver cleanup: %s", e)

    logger.info(f"[SHUTDOWN] {get_timestamp()} API shutdown completed")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Rankings App API",
    description="REST API and WebSocket server for Rankings App",
    version="1.0.0",
    lifespan=lifespan,
)

# Add request/response logging middleware (only in DEBUG mode)
if DEBUG_MODE and LoggingMiddleware:
    app.add_middleware(LoggingMiddleware)
    logger.info("Request/response logging middleware enabled (DEBUG mode)")

# Add request ID middleware for traceable logs and error responses.
app.add_middleware(RequestIdMiddleware)
logger.info("Request ID middleware enabled")

# Add global exception handler middleware (must be added before other middleware)
app.add_middleware(ExceptionHandlerMiddleware)
logger.info("Global exception handler middleware enabled")

# Sanitize JSON error bodies for non-admin clients (outer than exception handler on response path)
app.add_middleware(ErrorSanitizerMiddleware)
logger.info("Error sanitizer middleware enabled")

# Add Prometheus metrics middleware (early in chain to track all requests)
try:
    from api.middleware.prometheus import PrometheusMiddleware
    app.add_middleware(PrometheusMiddleware)
    logger.info("Prometheus metrics middleware enabled")
except ImportError as e:
    logger.warning("Prometheus middleware not available: %s", e)

# Per-IP rate limiting for login and rankings (returns 429 when exceeded)
try:
    from api.rate_limiter import check_login, check_rankings
except ImportError:
    check_login = check_rankings = None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Return 429 for /api/auth/login and /api/rankings/* when per-IP limit exceeded."""
    async def dispatch(self, request: StarletteRequest, call_next):
        if check_login is None or check_rankings is None:
            return await call_next(request)
        path = request.url.path
        # Login: POST only (avoid counting GET/OPTIONS)
        if path in ("/api/auth/login", "/api/v1/auth/login") and request.method == "POST":
            allowed, retry_after = check_login(request)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many login attempts. Try again later."},
                    headers={"Retry-After": str(int(retry_after) + 1)},
                )
        # Rankings: GET (and HEAD) only
        if request.method in ("GET", "HEAD") and (
            path.startswith("/api/rankings/") or path.startswith("/api/v1/rankings/")
        ):
            allowed, retry_after = check_rankings(request)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Try again later."},
                    headers={"Retry-After": str(int(retry_after) + 1)},
                )
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)


class HealthFailureLoggingMiddleware(BaseHTTPMiddleware):
    """Log ERROR when /api/health or /api/v1/health returns 5xx (for alerting)."""
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        path = request.url.path
        if path in ("/api/health", "/api/v1/health") and getattr(response, "status_code", 0) >= 500:
            logger.error("Health check failed: path=%s status=%s", path, getattr(response, "status_code", "?"))
        return response


app.add_middleware(HealthFailureLoggingMiddleware)

# API access control (docs/API_ACCESS_POLICY.md; implementation in api/middleware/access_control.py).
# Starlette runs the LAST added middleware first, so RequireApiKeyMiddleware (added second) runs
# before RequireUserOrAdminMiddleware. Both are added before CORS so CORS stays outermost and
# 401/403 responses still carry CORS headers.
app.add_middleware(RequireUserOrAdminMiddleware)
# DEBUG=true without BOT_API_KEY: key check disabled with a warning (local dev only); production
# refuses to start without BOT_API_KEY (_validate_production_security).
app.add_middleware(RequireApiKeyMiddleware, api_key=BOT_API_KEY, allow_missing_key=DEBUG_MODE)

# CORS middleware - allow React frontend (dev + production). Regex allows any subdomain/port on domain.
# localhost for dev; 127 reserved only for sensitive local-only services
_default_origins = [
    "http://localhost:5174",
    "http://localhost:3000",
    "https://probilliardssoftware.com",
    "http://probilliardssoftware.com",
    "https://www.probilliardssoftware.com",
    "http://www.probilliardssoftware.com",
    "https://app.probilliardssoftware.com",
    "http://app.probilliardssoftware.com",
    "https://example.com",
    "https://www.example.com",
    "http://example.com",
    "http://www.example.com",
]
_cors_env = os.getenv("CORS_ORIGINS", "").strip()
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env else _default_origins
# Use only explicit origins, no regex for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (unversioned: web app)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(auth_v1.router, prefix="/api/v1/auth", tags=["auth-v1"])
app.include_router(splash_v1.router, prefix="/api/v1", tags=["splash-v1"])
# Explicit routes for GET/POST /api/users (FastAPI empty path "" can fail with prefixed routers)
app.add_api_route("/api/users", list_users, methods=["GET"], response_model=UserListResponse)
app.add_api_route("/api/users", create_user, methods=["POST"], response_model=users.UserResponse)
app.include_router(users.router, tags=["users"])
app.include_router(rankings.router, prefix="/api/rankings", tags=["rankings"])
app.include_router(data_quality.router)
app.include_router(tournaments.router)  # Has its own prefix defined
app.include_router(leagues.router)  # League management
app.include_router(tours.router)  # Tour/series
app.include_router(tournament_wizard.router)  # Tournament wizard with interactive setup
app.include_router(tournament_history.router)  # Tournament history routes
app.include_router(player_performance.router)  # Player performance and stats
app.include_router(ai_coach.router)  # AI Coach routes (prefix=/api/ai-coach defined in router)
app.include_router(rankings_assistant.router)  # Role-scoped Ollama Q&A (prefix on router)
app.include_router(payments.router)  # Payment routes (prefix=/api/payments defined in router)
app.include_router(coupons.router)  # Coupon/promo routes (prefix=/api/coupon defined in router)
app.include_router(notifications.router)  # Notification preferences (prefix=/api/notifications)
app.include_router(fargo.router)  # FARGO ratings (prefix=/api/fargo)
app.include_router(rating_accuracy.router)  # Rating accuracy metrics (prefix=/api/rating-accuracy)
app.include_router(self_calibration.router)  # Self-calibration system (prefix=/api/self-calibration)
app.include_router(head_to_head.router)  # Head-to-head comparison
app.include_router(ai_narrative.router)  # Page-scoped AI Q&A
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(docs.router, prefix="/api/docs", tags=["docs"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(messages.router, prefix="/api/messages", tags=["messages"])
app.include_router(network.router, prefix="/api", tags=["network"])
app.include_router(email_test.router)
app.include_router(health.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(metrics.router)  # /metrics endpoint (no prefix, accessible without auth)
app.include_router(assets.router)
app.include_router(rules.router)
app.include_router(media.router)
app.include_router(admin.router)
app.include_router(admin_dev_tools.router)
app.include_router(events.router)
app.include_router(appearance.router)
app.include_router(covert_ops.router)
app.include_router(director.router)
app.include_router(alfa.router)
app.include_router(alfa_ratings.router)  # Alfa prediction and explanation endpoints
app.include_router(test_tournaments.router, prefix="/api/test-tournaments", tags=["test-tournaments"])
app.include_router(test_center_views.router, prefix="/api", tags=["test-center-views"])
app.include_router(login_features.router)
app.include_router(splash_config.router)
app.include_router(ui_customizations.router)
app.include_router(csv_import.router)
app.include_router(profile.router, prefix="/api", tags=["profile"])  # Profile customization (nickname, email)
app.include_router(admin_security.router, tags=["admin-security"])  # Admin security endpoints (bulk user, login monitoring)
app.include_router(backups.router)  # Database backup management (Admin only)
app.include_router(live_updates.router)  # Live updates SSE endpoint (prefix /api/live defined in router)

# Versioned API for mobile / stable contract (docs/PRODUCTION_AND_APP_CONVERSION.md)
# auth_v1.router is already mounted at /api/v1/auth on line 609
app.include_router(rankings.router, prefix="/api/v1/rankings", tags=["rankings-v1"])
app.include_router(system.router, prefix="/api/v1/system", tags=["system-v1"])
app.include_router(messages.router, prefix="/api/v1/messages", tags=["messages-v1"])
app.include_router(logs.router, prefix="/api/v1/logs", tags=["logs-v1"])
app.include_router(network.router, prefix="/api/v1", tags=["network-v1"])

@app.get("/api/v1/health")
async def health_check_v1():
    """Versioned health check for mobile/app clients."""
    return {
        "status": "healthy",
        "service": "Rankings Bot API",
        "version": "1.0.0",
        "api_version": "v1",
    }


@app.get("/api/v1/config")
async def config_v1():
    """App config for mobile (min version, maintenance). No auth required."""
    return {
        "minAppVersion": os.getenv("MOBILE_MIN_APP_VERSION", ""),
        "maintenanceMode": os.getenv("MAINTENANCE_MODE", "false").lower() == "true",
    }


@app.get("/api/app-version")
async def app_version():
    """App version, force-update floor, and API image build hash (frontend pairing check)."""
    return {
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "min_app_version": os.getenv("MIN_APP_VERSION", "1.0.0"),
        "build_hash": get_build_hash(),
    }


@app.get("/privacy", include_in_schema=False)
async def privacy_policy():
    """Privacy policy page (required for App Store)."""
    html = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Privacy Policy</title></head>
<body style="font-family:sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.6">
<h1>Privacy Policy</h1>
<p><strong>Last updated:</strong> 2026</p>
<p>Pro Billiards Software ("we") operates the Rankings App and related services. This policy describes what information we collect and how we use it.</p>
<h2>Information We Collect</h2>
<ul>
<li><strong>Account data:</strong> Username, email, password (hashed) when you register.</li>
<li><strong>Usage data:</strong> Rankings views, tournament data, and API requests to provide the service.</li>
<li><strong>Payment data:</strong> Processed by Stripe; we do not store full card details.</li>
</ul>
<h2>How We Use It</h2>
<p>To operate the service, authenticate users, process payments, and improve the app.</p>
<h2>Sharing</h2>
<p>We do not sell your data. We may share with service providers (hosting, Stripe) as needed to operate the service.</p>
<h2>Security</h2>
<p>We use HTTPS, secure storage for credentials, and industry-standard practices.</p>
<h2>Contact</h2>
<p>Questions: contact via the website or app settings.</p>
</body></html>
"""
    return HTMLResponse(content=html)

# Serve SPA from same backend when frontend/dist exists (Nginx often still proxies to API :8003).
_project_root = Path(__file__).resolve().parent.parent
_frontend_dist = _project_root / "frontend" / "dist"
_frontend_index = _frontend_dist / "index.html"
# Require index.html — partial builds (assets/ only) must not mount SPA or FileResponse raises.
if (
    _frontend_dist.is_dir()
    and (_frontend_dist / "assets").is_dir()
    and _frontend_index.is_file()
):
    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="assets")
    @app.get("/")
    async def root():
        return FileResponse(
            _frontend_index,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )
    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        if path.startswith("api") or path in ("docs", "redoc") or path.startswith("openapi"):
            raise HTTPException(status_code=404, detail="Not Found")
        # Prevent path traversal
        file_path = (_frontend_dist / path).resolve()
        if not str(file_path).startswith(str(_frontend_dist.resolve())):
            raise HTTPException(status_code=404, detail="Not Found")
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(
            _frontend_index,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )
else:
    @app.get("/")
    async def root():
        return {
            "message": "Rankings App API",
            "version": "1.0.0",
            "docs": "/api/docs",
            "health": "/api/health"
        }
    # When frontend/dist is missing, non-API paths return a clear message instead of generic 404
    @app.get("/{path:path}")
    async def no_frontend_fallback(path: str):
        if path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not Found")
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Frontend not deployed",
                "message": "Build and sync frontend/dist to this server, then restart the API. See scripts/deploy.sh and web-sites-server/DEPLOY_NOW.md.",
                "api_health": "/api/health",
                "api_docs": "/api/docs",
            },
        )

# WebSocket endpoint for real-time updates
# Note: Clients may see close code 1012 (Service Restart) after API/nginx restarts or deploy; they should reconnect.
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    """WebSocket endpoint for real-time updates with user context"""
    from api.notifications import connect_live_updates

    logger.info("WebSocket connection attempt received")
    try:
        # Extract token from query parameters or headers
        auth_token = token
        if not auth_token:
            # Try to get from headers
            auth_header = websocket.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                auth_token = auth_header[7:]

        user_info = None
        if auth_token:
            try:
                # Decode and validate the JWT token
                SECRET_KEY = os.getenv("JWT_SECRET")
                payload = jwt.decode(auth_token, SECRET_KEY, algorithms=["HS256"])
                from starlette.concurrency import run_in_threadpool
                if await run_in_threadpool(auth_lib.password_change_pending, payload):
                    raise ValueError("password change required; treating connection as anonymous")
                user_info = {
                    "username": payload.get("sub"),
                    "role": payload.get("role", "user"),
                    "permissions": [],  # Could be expanded based on role
                    "payment_features": []  # Could be populated from user profile
                }
            except Exception as e:
                logger.warning("Invalid JWT token in WebSocket connection: %s", e)

        await connect_live_updates(websocket, user_info)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8003"))
    log_level = "debug" if DEBUG_MODE else "info"

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=port,
        log_level=log_level,
        reload=False,
        access_log=True
    )
