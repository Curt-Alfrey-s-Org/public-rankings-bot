#!/usr/bin/env python3
"""
Enrich all players missing Fargo ratings.
Uses FairMatch scraper with rate limiting to avoid overwhelming the server.

Rate Limiting (3 runs per day):
- Log execution to prevent more than 3 runs per day
- Each run processes ALL missing players in batches
- 1.5 second delay between individual lookups
- 5 second delay between 25-player batches

Usage:
    python3 enrich_all_fargo.py                  # Dry run (show what would be scraped)
    python3 enrich_all_fargo.py --execute        # Actually scrape and update DB
    python3 enrich_all_fargo.py --system WPBA    # Only WPBA_Women
    python3 enrich_all_fargo.py --system WPA     # WPA_Women AND WPA_Men
"""

import argparse
import sys
import time
import logging
import os
import shutil
from pathlib import Path
from datetime import datetime, date

logging.basicConfig(
    level=logging.INFO,
   format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Ensure CHROME_PATH is set for FairMatch scraper
if not os.environ.get("CHROME_PATH"):
    # Auto-detect Chrome binary
    chrome_options = [
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/snap/bin/chromium",
        "/usr/bin/google-chrome",
    ]
    for chrome_path in chrome_options:
        if Path(chrome_path).exists():
            os.environ["CHROME_PATH"] = chrome_path
            logger.info(f"Auto-detected Chrome at: {chrome_path}")
            break

# Add project to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "Rankings-Bot"))

from database import get_database_manager

# Import FairMatch scraper directly without hitting __init__.py
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "fairmatch_scraper",
        PROJECT_ROOT / "Rankings-Bot/api/services/fairmatch_scraper.py"
    )
    fairmatch_scraper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fairmatch_scraper)
    lookup_rating = fairmatch_scraper.lookup_rating
    cleanup_persistent_driver = fairmatch_scraper.cleanup_persistent_driver
    SELENIUM_AVAILABLE = fairmatch_scraper.SELENIUM_AVAILABLE
except Exception as e:
    logger.error(f"Could not load fairmatch_scraper: {e}")
    SELENIUM_AVAILABLE = False
    def lookup_rating(name):
        return None, "Scraper not available"
    def cleanup_persistent_driver():
        pass

RATE_LIMIT_FILE = PROJECT_ROOT / ".fargo_scrape_log"
MAX_RUNS_PER_DAY = 3
LOOKUP_DELAY = 1.5  # Seconds between individual lookups
BATCH_DELAY = 5.0   # Seconds between 25-player batches
BATCH_SIZE = 25


def check_rate_limit() -> bool:
    """Check if we can run today (max 3 runs per day)."""
    if not RATE_LIMIT_FILE.exists():
        return True
    
    with open(RATE_LIMIT_FILE, 'r') as f:
        lines = f.readlines()
    
    today = date.today().isoformat()
    today_runs = sum(1 for line in lines if line.startswith(today))
    
    if today_runs >= MAX_RUNS_PER_DAY:
        logger.error(f"❌ Rate limit exceeded: {today_runs} runs already today (max {MAX_RUNS_PER_DAY})")
        logger.info(f"   Last runs: {[l.strip() for l in lines[-3:]]}")
        return False
    
    logger.info(f"✓ Rate limit OK: {today_runs}/{MAX_RUNS_PER_DAY} runs today")
    return True


def log_run(stats: dict):
    """Log this run to rate limit file."""
    with open(RATE_LIMIT_FILE, 'a') as f:
        f.write(f"{date.today().isoformat()} {datetime.now().strftime('%H:%M:%S')} "
                f"searched={stats['searched']} found={stats['found']} failed={stats['failed']}\n")


def get_missing_players(db, system: str = None) -> list:
    """Get all players missing Fargo ratings.
    
    Args:
        db: DatabaseManager instance
        system: 'WPBA', 'WPA', or None (all systems)
    
    Returns:
        List of (player_name, ranking_system) tuples
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    
    if system == 'WPBA':
        systems = ['WPBA_Women']
    elif system == 'WPA':
        systems = ['WPA_Women', 'WPA_Men', 'WPA_Heyball', 'WPA_Heyball_Men', 'WPA_Heyball_Women']
    else:
        systems = ['WPBA_Women', 'WPA_Women', 'WPA_Men', 'WPA_Heyball', 'WPA_Heyball_Men', 'WPA_Heyball_Women']
    
    placeholders = ', '.join(['?' for _ in systems])
    
    # PostgreSQL requires ORDER BY columns in SELECT when using DISTINCT
    cursor.execute(f"""
        SELECT player_name, ranking_system, rank
        FROM rankings
        WHERE ranking_system IN ({placeholders})
          AND fargo_rating IS NULL
          AND snapshot_date = (
              SELECT MAX(snapshot_date) 
              FROM rankings 
              WHERE ranking_system = rankings.ranking_system
          )
        ORDER BY ranking_system, rank
    """, tuple(systems))
    
    players = cursor.fetchall()
    conn.close()
    
    # Return unique (player_name, ranking_system) pairs
    seen = set()
    result = []
    for row in players:
        key = (row[0], row[1])
        if key not in seen:
            seen.add(key)
            result.append(key)
    
    return result


def update_fargo_rating(db, player_name: str, rating: float):
    """Update Fargo rating for a player across all their rankings."""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE rankings
        SET fargo_rating = ?,
            fargo_last_updated = CURRENT_TIMESTAMP
        WHERE player_name = ?
          AND fargo_rating IS NULL
    """, (rating, player_name))
    
    updated = cursor.rowcount
    conn.commit()
    conn.close()
    
    return updated


def scrape_player(player_name: str) -> tuple:
    """Scrape Fargo rating for one player.
    
    Returns:
        (rating, error_message) tuple
    """
    try:
        rating, error = lookup_rating(player_name)
        return rating, error
    except Exception as e:
        return None, str(e)


def enrich_fargo(db, system: str = None, dry_run: bool = True):
    """Enrich all players missing Fargo ratings.
    
    Args:
        db: DatabaseManager instance
        system: 'WPBA', 'WPA', or None (all)
        dry_run: If True, only show what would be done
    """
    # Check Selenium availability
    if not SELENIUM_AVAILABLE:
        logger.error("❌ Selenium not available. Install with: pip install selenium")
        logger.error("   Also need Chrome/Chromium installed")
        return
    
    # Check rate limit
    if not dry_run and not check_rate_limit():
        return
    
    # Get missing players
    logger.info(f"🔍 Finding players missing Fargo ratings (system={system or 'ALL'})...")
    missing = get_missing_players(db, system)
    
    if not missing:
        logger.info("✓ All players already have Fargo ratings!")
        return
    
    # Group by system for summary
    by_system = {}
    for name, sys in missing:
        by_system.setdefault(sys, []).append(name)
    
    logger.info(f"\n📊 Players Missing Fargo Ratings:")
    logger.info("=" * 60)
    total = 0
    for sys in sorted(by_system.keys()):
        count = len(by_system[sys])
        total += count
        logger.info(f"  {sys:15} : {count:3} players")
    logger.info("=" * 60)
    logger.info(f"  {'TOTAL':15} : {total:3} players")
    logger.info("")
    
    if dry_run:
        logger.info("🔸 DRY RUN MODE - No actual scraping")
        logger.info("   Run with --execute to actually scrape")
        logger.info(f"\n📝 Would scrape {total} players:")
        logger.info(f"   - Lookup delay: {LOOKUP_DELAY}s between players")
        logger.info(f"   - Batch delay: {BATCH_DELAY}s every {BATCH_SIZE} players")
        logger.info(f"   - Estimated time: {(total * LOOKUP_DELAY + (total // BATCH_SIZE) * BATCH_DELAY) / 60:.1f} minutes")
        return
    
    # Actually scrape
    logger.info(f"🚀 Starting Fargo enrichment for {total} players")
    logger.info(f"   Rate limit: {LOOKUP_DELAY}s per lookup, {BATCH_DELAY}s per {BATCH_SIZE} batch")
    logger.info("")
    
    stats = {'searched': 0, 'found': 0, 'failed': 0, 'updated': 0}
    start_time = time.time()
    
    for i, (player_name, sys) in enumerate(missing, 1):
        # Batch delay
        if i > 1 and (i - 1) % BATCH_SIZE == 0:
            logger.info(f"⏸  Batch complete ({i-1}/{total}), waiting {BATCH_DELAY}s...")
            time.sleep(BATCH_DELAY)
        
        logger.info(f"[{i}/{total}] {sys:15} | {player_name}")
        
        # Scrape
        rating, error = scrape_player(player_name)
        stats['searched'] += 1
        
        if rating:
            # Update database
            updated = update_fargo_rating(db, player_name, rating)
            stats['found'] += 1
            stats['updated'] += updated
            logger.info(f"          ✓ Found: {rating} (updated {updated} records)")
        else:
            stats['failed'] += 1
            logger.warning(f"          ✗ Not found: {error or 'No rating'}")
        
        # Delay before next lookup
        if i < total:
            time.sleep(LOOKUP_DELAY)
    
    elapsed = time.time() - start_time
    
    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("✅ Fargo Enrichment Complete")
    logger.info("=" * 60)
    logger.info(f"  Searched:  {stats['searched']:3}")
    logger.info(f"  Found:     {stats['found']:3} ({stats['found']/stats['searched']*100:.1f}%)")
    logger.info(f"  Failed:    {stats['failed']:3} ({stats['failed']/stats['searched']*100:.1f}%)")
    logger.info(f"  Updated:   {stats['updated']:3} database records")
    logger.info(f"  Time:      {elapsed/60:.1f} minutes")
    logger.info("=" * 60)
    
    # Log run
    log_run(stats)


def main():
    parser = argparse.ArgumentParser(description="Enrich missing Fargo ratings")
    parser.add_argument('--execute', action='store_true', 
                       help='Actually scrape (default: dry run)')
    parser.add_argument('--system', choices=['WPBA', 'WPA'],
                       help='Only scrape specific system (WPBA=Women, WPA=Women+Men)')
    args = parser.parse_args()
    
    logger.info("🎱 Fargo Rating Enrichment Tool")
    logger.info("=" * 60)
    logger.info(f"  Mode:   {'EXECUTE' if args.execute else 'DRY RUN'}")
    logger.info(f"  System: {args.system or 'ALL'}")
    logger.info("=" * 60)
    logger.info("")

    # Initialize database
    db = get_database_manager()

    try:
        # Run enrichment
        enrich_fargo(db, system=args.system, dry_run=not args.execute)
    except KeyboardInterrupt:
        logger.info("Interrupted — cleaning up Chrome driver")
    finally:
        # Always cleanup Chrome driver (prevents orphaned processes on interrupt/exit)
        try:
            cleanup_persistent_driver()
        except Exception as e:
            logger.warning(f"Cleanup: {e}")


if __name__ == "__main__":
    main()
