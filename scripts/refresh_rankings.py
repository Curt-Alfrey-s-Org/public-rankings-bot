#!/usr/bin/env python3
"""
Refresh current rankings (WPBA + WPA divisions + Artistic + Fargo table).
For cron/systemd use without API auth.

Scrapers use dedicated modules under scrapers/*_scraper.py with explicit timeouts.
"""

import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from database import get_database_manager
from scrapers.wpba_rankings_scraper import scrape_wpba_rankings
from scrapers.wpa_men_scraper import scrape_wpa_men_rankings
from scrapers.wpa_women_scraper import scrape_wpa_women_rankings
from scrapers.wpa_heyball_men_scraper import scrape_wpa_heyball_men_rankings
from scrapers.wpa_heyball_women_scraper import scrape_wpa_heyball_women_rankings
from scrapers.wpa_artistic_scraper import scrape_wpa_artistic_rankings
from scrapers.fargo_rankings_scraper import scrape_fargo_rankings_into_table

LOG_LEVEL = os.environ.get("REFRESH_VERBOSE", "").strip().lower() in ("1", "true", "yes")
REFRESH_STALE_HOURS = int(os.environ.get("REFRESH_STALE_HOURS", "24"), 10)
REFRESH_SCRAPER_TIMEOUT_SEC = float(os.environ.get("REFRESH_SCRAPER_TIMEOUT_SEC", "180"))

logging.basicConfig(
    level=logging.INFO if LOG_LEVEL else logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def _with_timeout(label: str, fn: Callable[[], Any], timeout_sec: float) -> Tuple[Any, Optional[str]]:
    """Run fn in a worker thread; return (result, error_message)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        try:
            return fut.result(timeout=timeout_sec), None
        except FuturesTimeoutError:
            return None, f"{label} timed out after {timeout_sec}s"
        except Exception as exc:
            return None, str(exc)


def _scrape_wpba() -> Tuple[Optional[list], Optional[str]]:
    return _with_timeout(
        "WPBA",
        scrape_wpba_rankings,
        REFRESH_SCRAPER_TIMEOUT_SEC,
    )


def _scrape_wpa_bundle() -> Tuple[Optional[dict], Optional[str]]:
    def _run():
        scraper_timeout = REFRESH_SCRAPER_TIMEOUT_SEC
        women, e1 = _with_timeout("WPA Women", scrape_wpa_women_rankings, scraper_timeout)
        if e1:
            logger.warning("WPA women: %s", e1)
        men, e2 = _with_timeout("WPA Men", scrape_wpa_men_rankings, scraper_timeout)
        if e2:
            logger.warning("WPA men: %s", e2)
        hb_men, e3 = _with_timeout("Heyball Men", scrape_wpa_heyball_men_rankings, scraper_timeout)
        if e3:
            logger.warning("Heyball men: %s", e3)
        hb_women, e4 = _with_timeout("Heyball Women", scrape_wpa_heyball_women_rankings, scraper_timeout)
        if e4:
            logger.warning("Heyball women: %s", e4)
        artistic, e5 = _with_timeout("Artistic", scrape_wpa_artistic_rankings, scraper_timeout)
        if e5:
            logger.warning("Artistic: %s", e5)
        if not women and not men and not hb_men and not hb_women and not artistic:
            return None
        return {
            "women": women or [],
            "men": men or [],
            "heyball_men": hb_men or [],
            "heyball_women": hb_women or [],
            "artistic": artistic or [],
        }

    return _with_timeout("WPA bundle", _run, REFRESH_SCRAPER_TIMEOUT_SEC * 5)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh WPBA/WPA rankings and store in Postgres")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore staleness check (REFRESH_STALE_HOURS) and refresh now.",
    )
    parser.add_argument("--wpba-only", action="store_true", help="Only refresh WPBA")
    parser.add_argument("--wpa-only", action="store_true", help="Only refresh WPA (+ artistic)")
    args = parser.parse_args()

    db = get_database_manager()
    run_wpba = not args.wpa_only
    run_wpa = not args.wpba_only

    if not args.force and hasattr(db, "check_startup_refresh_needed"):
        try:
            refresh_check = db.check_startup_refresh_needed(stale_threshold_hours=REFRESH_STALE_HOURS)
            if not refresh_check.get("needs_refresh", True):
                logger.info("Rankings are fresh (REFRESH_STALE_HOURS=%s); skipping refresh", REFRESH_STALE_HOURS)
                return 0
        except Exception as exc:
            logger.warning("Staleness check failed; continuing with refresh: %s", exc)

    wpba_data = None
    wpba_err = None
    wpa_bundle = None
    wpa_err = None

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_wpba = pool.submit(_scrape_wpba) if run_wpba else None
        fut_wpa = pool.submit(_scrape_wpa_bundle) if run_wpa else None
        if fut_wpba is not None:
            wpba_data, wpba_err = fut_wpba.result()
        if fut_wpa is not None:
            wpa_bundle, wpa_err = fut_wpa.result()

    logger.info("Scrape stage completed in %.2fs", time.perf_counter() - start)

    ok = False
    rankings_saved = False

    if run_wpba:
        if wpba_data:
            count = db.save_wpba_rankings(wpba_data, ranking_type="WPBA_Women")
            ok = True
            rankings_saved = True
            logger.info("WPBA refreshed: %s rows", count)
            if hasattr(db, "split_wpba_women_to_column_buttons"):
                try:
                    logger.info("WPBA women column split: %s", db.split_wpba_women_to_column_buttons())
                except Exception as exc:
                    logger.warning("WPBA women column split failed: %s", exc)
            if hasattr(db, "fill_tournament_history_from_wpba_women_events"):
                try:
                    th_stats = db.fill_tournament_history_from_wpba_women_events()
                    logger.info("WPBA tournament history upsert: %s", th_stats)
                except Exception as exc:
                    logger.warning("WPBA tournament history fill failed: %s", exc)
        else:
            logger.error("WPBA refresh failed: %s", wpba_err or "unknown error")

    if run_wpa:
        if wpa_bundle:
            women_count = 0
            men_count = 0
            heyball_men_count = 0
            heyball_women_count = 0
            artistic_count = 0
            if wpa_bundle.get("women"):
                women_count = db.save_wpa_rankings(wpa_bundle["women"], ranking_type="WPA_Women")
                ok = True
                rankings_saved = True
            if wpa_bundle.get("men"):
                men_count = db.save_wpa_rankings(wpa_bundle["men"], ranking_type="WPA_Men")
                ok = True
                rankings_saved = True
            if wpa_bundle.get("heyball_men"):
                heyball_men_count = db.save_wpa_rankings(
                    wpa_bundle["heyball_men"], ranking_type="WPA_Heyball_Men"
                )
                ok = True
                rankings_saved = True
            if wpa_bundle.get("heyball_women"):
                heyball_women_count = db.save_wpa_rankings(
                    wpa_bundle["heyball_women"], ranking_type="WPA_Heyball_Women"
                )
                ok = True
                rankings_saved = True
            if wpa_bundle.get("artistic"):
                artistic_count = db.save_wpa_rankings(
                    wpa_bundle["artistic"], ranking_type="WPA_Artistic"
                )
                ok = True
                rankings_saved = True

            if women_count > 0 and hasattr(db, "split_wpa_women_to_column_buttons"):
                try:
                    logger.info("WPA women split refreshed: %s", db.split_wpa_women_to_column_buttons())
                except Exception as exc:
                    logger.warning("WPA women split refresh failed: %s", exc)
            if men_count > 0 and hasattr(db, "split_wpa_men_to_column_buttons"):
                try:
                    logger.info("WPA men split refreshed: %s", db.split_wpa_men_to_column_buttons())
                except Exception as exc:
                    logger.warning("WPA men split refresh failed: %s", exc)
            if heyball_men_count > 0 and hasattr(db, "split_wpa_heyball_men_to_column_buttons"):
                try:
                    logger.info("WPA heyball men split refreshed: %s", db.split_wpa_heyball_men_to_column_buttons())
                except Exception as exc:
                    logger.warning("WPA heyball men split refresh failed: %s", exc)
            if heyball_women_count > 0 and hasattr(db, "split_wpa_heyball_women_to_column_buttons"):
                try:
                    logger.info(
                        "WPA heyball women split refreshed: %s",
                        db.split_wpa_heyball_women_to_column_buttons(),
                    )
                except Exception as exc:
                    logger.warning("WPA heyball women split refresh failed: %s", exc)
            if artistic_count > 0 and hasattr(db, "split_wpa_artistic_to_column_buttons"):
                try:
                    logger.info("WPA artistic split refreshed: %s", db.split_wpa_artistic_to_column_buttons())
                except Exception as exc:
                    logger.warning("WPA artistic split refresh failed: %s", exc)

            logger.info(
                "WPA refreshed: women=%s men=%s hb_men=%s hb_women=%s artistic=%s",
                women_count,
                men_count,
                heyball_men_count,
                heyball_women_count,
                artistic_count,
            )
        else:
            logger.error("WPA refresh failed: %s", wpa_err or "unknown error")

    # Fargo dedicated table (from players scores -- bounded)
    try:
        fn, ferr = _with_timeout(
            "Fargo table",
            scrape_fargo_rankings_into_table,
            min(60.0, REFRESH_SCRAPER_TIMEOUT_SEC),
        )
        if ferr:
            logger.warning("Fargo table refresh: %s", ferr)
        elif fn:
            ok = True
            logger.info("Fargo association table refreshed: %s rows", fn)
    except Exception as exc:
        logger.warning("Fargo table refresh failed: %s", exc)

    if rankings_saved and hasattr(db, "refresh_materialized_views"):
        try:
            db.refresh_materialized_views()
            logger.info("Refreshed materialized views after rankings refresh script")
        except Exception as exc:
            logger.warning("Materialized view refresh failed: %s", exc)
        try:
            from api.services.cache_store import invalidate_cache

            invalidate_cache("tournament-history")
        except Exception as exc:
            logger.warning("Tournament history cache invalidate failed: %s", exc)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
