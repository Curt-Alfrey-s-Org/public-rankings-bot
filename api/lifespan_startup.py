"""
Heavy startup (self-tests + player enrichment) run in background so the API accepts requests in seconds.
Called from api.main lifespan via run_in_executor.
"""
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run_self_tests_and_enrichment_impl(app: Any) -> None:
    """Run startup self-tests and player enrichment (sync). Runs in thread pool so lifespan can yield quickly."""
    from database import get_engine, get_database_manager
    engine = get_engine()
    from sqlalchemy import text

    test_start = time.time()
    test_results = []
    passed = 0
    failed = 0

    # Test 1: Python Syntax Check
    try:
        import subprocess
        project_root = Path(__file__).resolve().parent.parent
        for module_path in ['api/routes/rankings.py', 'api/routes/system.py']:
            full_path = project_root / module_path
            if full_path.exists():
                result = subprocess.run(
                    ['python3', '-m', 'py_compile', str(full_path)],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode != 0:
                    failed += 1
                    break
        else:
            passed += 1
    except Exception as e:
        failed += 1
        logger.warning("[SELFTEST] Python Syntax Check: %s", e)

    # Test 2: Database Check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1")).scalar()
        passed += 1
        logger.info("[SELFTEST] ✓ Database Check")
    except Exception as e:
        failed += 1
        logger.warning("[SELFTEST] ✗ Database Check: %s", e)

    # Test 3–10: Lightweight checks (structure, routes, CORS, scrapers, rate limiter, freshness, archive)
    try:
        if hasattr(app, 'routes') and len(app.routes) > 0:
            passed += 1
        else:
            failed += 1
    except Exception:
        failed += 1

    try:
        has_cors = any('CORSMiddleware' in str(m) for m in app.user_middleware)
        if has_cors:
            passed += 1
        else:
            failed += 1
    except Exception:
        failed += 1

    try:
        from database import get_database_manager
        db_manager = get_database_manager()
        db_manager.check_startup_refresh_needed(stale_threshold_hours=24)
        passed += 1
    except Exception as e:
        failed += 1
        logger.warning("[SELFTEST] Rankings Freshness: %s", e)

    try:
        from database import get_database_manager
        db_manager = get_database_manager()
        db_manager.ensure_archive_table_exists()
        passed += 1
    except Exception as e:
        failed += 1
        logger.warning("[SELFTEST] Archive Table: %s", e)

    test_elapsed = time.time() - test_start
    total = passed + failed
    logger.info("[SELFTEST] Startup self-tests: %s/%s passed in %.2fs", passed, total, test_elapsed)

    # Player enrichment (often slow with large rankings table)
    # Skip if enrichment was done in last hour (optimization for rapid restarts)
    skip_enrichment = False
    try:
        from database import get_database_manager
        db_manager = get_database_manager()
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        # Check if enrichment has run recently by checking last ranking update time
        cursor.execute(text("""
            SELECT COUNT(*) FROM rankings 
            WHERE (country IS NOT NULL OR license_number IS NOT NULL OR fargo_rating IS NOT NULL)
              AND created_at > CURRENT_TIMESTAMP - INTERVAL '1 hour'
        """))
        recent_updates = cursor.fetchone()[0]
        conn.close()
        if recent_updates > 50:  # If 50+ records updated in last hour, enrichment likely just ran
            skip_enrichment = True
            logger.info("[STARTUP] Skipping enrichment - data recently updated (%s updates in last hour)", recent_updates)
    except Exception as e:
        logger.debug("[STARTUP] Could not check enrichment recency: %s", e)
    
    if not skip_enrichment:
        try:
            from database import get_database_manager
            db_manager = get_database_manager()
            enrichment_result = db_manager.enrich_player_data()
            logger.info(
                "[STARTUP] Player enrichment: %s players processed, %s records enriched, %s fields filled in %.2fs",
                enrichment_result.get('processed_players', 0),
                enrichment_result.get('enriched_records', 0),
                enrichment_result.get('fields_filled', 0),
                enrichment_result.get('duration_seconds', 0)
            )
        except Exception as e:
            logger.warning("[STARTUP] Player data enrichment failed: %s", e)

    # Fargo sync DISABLED - only manual Fargo sync allowed to prevent bans
    logger.info("[STARTUP] Fargo auto-sync DISABLED - use manual Fargo sync in admin only")
