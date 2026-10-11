#!/usr/bin/env python3
"""
Enhanced Tournament History Scraper with:
- Rate limiting to avoid overwhelming source websites
- Incremental scraping (only new/updated tournaments)
- Robust error handling and retries
- Health monitoring and detailed logging
- Separate handling of past vs. future tournaments
- Automatic Fargo rating attachment
- Timestamp tracking for last updates
"""

import re
import logging
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Rate limiting configuration
RATE_LIMIT_DELAY = 2.0  # seconds between requests
MAX_RETRIES = 3
RETRY_DELAY = 5.0  # seconds

# Scraper health metrics
class ScraperMetrics:
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.events_discovered = 0
        self.events_processed = 0
        self.events_updated = 0
        self.events_new = 0
        self.events_future = 0
        self.errors = []
        self.warnings = []
        
    def to_dict(self):
        return {
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else None,
            "events_discovered": self.events_discovered,
            "events_processed": self.events_processed,
            "events_updated": self.events_updated,
            "events_new": self.events_new,
            "events_future": self.events_future,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors[:10],  # Limit to avoid huge logs
            "warnings": self.warnings[:10],
        }


class EnhancedTournamentScraper:
    """Enhanced tournament scraper with rate limiting, incremental updates, and monitoring."""
    
    def __init__(self, engine, rate_limit_delay: float = RATE_LIMIT_DELAY):
        self._engine = engine
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self.metrics = ScraperMetrics()
        
        from database.postgres_manager import PostgresManager
        self._db = PostgresManager(engine=engine)
        
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def get_connection(self):
        """Get database connection."""
        return self._db.get_connection()
    
    def _ensure_scraper_metadata_table(self):
        """Create table to track scraper runs and last update times."""
        from sqlalchemy import text
        conn = self._engine.connect()
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tournament_scraper_metadata (
                    id SERIAL PRIMARY KEY,
                    tournament_id VARCHAR(255) UNIQUE,
                    last_scraped_at TIMESTAMP,
                    last_updated_at TIMESTAMP,
                    scrape_count INTEGER DEFAULT 0,
                    last_scrape_status VARCHAR(32),
                    last_error TEXT
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tournament_scraper_runs (
                    id SERIAL PRIMARY KEY,
                    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    duration_seconds DOUBLE PRECISION,
                    events_discovered INTEGER DEFAULT 0,
                    events_processed INTEGER DEFAULT 0,
                    events_new INTEGER DEFAULT 0,
                    events_updated INTEGER DEFAULT 0,
                    events_future INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    warning_count INTEGER DEFAULT 0,
                    metrics_json TEXT
                )
            """))
            conn.commit()
            logger.debug("✅ Scraper metadata tables ensured")
        except Exception as e:
            logger.warning(f"Error creating metadata tables: {e}")
        finally:
            conn.close()
    
    def _get_last_scraped_time(self, tournament_id: str) -> Optional[datetime]:
        """Get when a tournament was last scraped successfully."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT last_scraped_at FROM tournament_scraper_metadata
                WHERE tournament_id = %s AND last_scrape_status = 'success'
            """, (tournament_id,))
            row = cursor.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(str(row[0]))
        except Exception as e:
            logger.debug(f"Error getting last scrape time for {tournament_id}: {e}")
        finally:
            conn.close()
        return None
    
    def _update_scraper_metadata(self, tournament_id: str, status: str, error: Optional[str] = None):
        """Update metadata after scraping a tournament."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO tournament_scraper_metadata 
                (tournament_id, last_scraped_at, last_updated_at, scrape_count, last_scrape_status, last_error)
                VALUES (%s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, %s, %s)
                ON CONFLICT (tournament_id) DO UPDATE SET
                last_scraped_at = CURRENT_TIMESTAMP,
                last_updated_at = CURRENT_TIMESTAMP,
                scrape_count = tournament_scraper_metadata.scrape_count + 1,
                last_scrape_status = EXCLUDED.last_scrape_status,
                last_error = EXCLUDED.last_error
            """, (tournament_id, status, error))
            conn.commit()
        except Exception as e:
            logger.warning(f"Error updating scraper metadata: {e}")
        finally:
            conn.close()
    
    def _save_scraper_run(self):
        """Save metrics for this scraper run."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            m = self.metrics
            cursor.execute("""
                INSERT INTO tournament_scraper_runs
                (run_timestamp, duration_seconds, events_discovered, events_processed,
                 events_new, events_updated, events_future, error_count, warning_count, metrics_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                m.start_time,
                (m.end_time - m.start_time).total_seconds() if m.start_time and m.end_time else None,
                m.events_discovered,
                m.events_processed,
                m.events_new,
                m.events_updated,
                m.events_future,
                len(m.errors),
                len(m.warnings),
                json.dumps(m.to_dict())
            ))
            conn.commit()
            logger.info("✅ Scraper run metrics saved")
        except Exception as e:
            logger.warning(f"Error saving scraper run: {e}")
        finally:
            conn.close()
    
    def _should_scrape_tournament(self, tournament_id: str, event_date: Optional[str], 
                                  force: bool = False) -> bool:
        """Determine if a tournament should be scraped based on last scrape time."""
        if force:
            return True
        
        # Future tournaments: scrape more frequently (every run)
        if event_date:
            try:
                evt_date = datetime.fromisoformat(event_date).date() if isinstance(event_date, str) else event_date
                if evt_date >= datetime.now().date():
                    return True  # Always scrape future tournaments
            except Exception as e:
                logger.debug("Could not parse event date '%s' for incremental scrape check: %s", event_date, e)
        
        # Past tournaments: only scrape if not scraped in last 7 days
        last_scraped = self._get_last_scraped_time(tournament_id)
        if last_scraped is None:
            return True  # Never scraped
        
        age = datetime.now() - last_scraped
        if age < timedelta(days=7):
            logger.debug(f"Skipping {tournament_id}: scraped {age.days} days ago")
            return False
        
        return True
    
    def init_tournament_tables(self):
        """Initialize all tournament tables including metadata tables."""
        from scrapers.tournament_history_scraper import TournamentHistoryScraper
        base_scraper = TournamentHistoryScraper(engine=self._engine)
        base_scraper.init_tournament_tables()
        self._ensure_scraper_metadata_table()
    
    def scrape_tournaments(
        self,
        wpba: bool = True,
        wpa: bool = True,
        include_future: bool = True,
        attach_fargo: bool = True,
        force_rescrape: bool = False,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Scrape tournaments with rate limiting, incremental updates, and monitoring.
        
        Args:
            wpba: Scrape WPBA tournaments
            wpa: Scrape WPA tournaments
            include_future: Include upcoming tournaments
            attach_fargo: Attach current Fargo ratings to player results
            force_rescrape: Force rescraping even if recently scraped
            limit: Maximum number of tournaments to process (for testing)
        
        Returns:
            Dictionary with scraping metrics
        """
        self.metrics = ScraperMetrics()
        self.metrics.start_time = datetime.now()
        
        logger.info("🔍 Starting enhanced tournament scraper")
        logger.info(f"   WPBA: {wpba}, WPA: {wpa}, Future: {include_future}, Fargo: {attach_fargo}")
        
        try:
            self.init_tournament_tables()
            
            # Discover events with rate limiting
            from scrapers.tournament_history_discovery import discover_past_events
            from scrapers.tournament_bracket_parser import get_tournament_results
            
            # PAST TOURNAMENTS
            logger.info("📅 Discovering past tournaments...")
            self._rate_limit()
            past_events = discover_past_events(wpba=wpba, wpa=wpa, include_future=False)
            self.metrics.events_discovered += len(past_events)
            logger.info(f"   Found {len(past_events)} past events")
            
            # FUTURE TOURNAMENTS
            future_events = []
            if include_future:
                logger.info("🔮 Discovering future tournaments...")
                self._rate_limit()
                future_events = discover_past_events(wpba=wpba, wpa=wpa, include_future=True)
                future_events = [e for e in future_events if self._is_future_event(e)]
                self.metrics.events_discovered += len(future_events)
                self.metrics.events_future = len(future_events)
                logger.info(f"   Found {len(future_events)} future events")
            
            all_events = past_events + future_events
            if limit:
                all_events = all_events[:limit]
            
            # Fargo cache
            fargo_cache = {}
            if attach_fargo:
                fargo_cache = self._fetch_fargo_cache()
            
            # Process events with incremental logic
            conn = self.get_connection()
            cursor = conn.cursor()
            
            try:
                for idx, ev in enumerate(all_events, 1):
                    tournament_id = self._slug_tournament_id(
                        ev.get("name", ""), 
                        ev.get("year", 0), 
                        ev.get("association", "WPBA")
                    )
                    
                    # Incremental scraping: skip if recently processed
                    if not self._should_scrape_tournament(tournament_id, ev.get("date"), force_rescrape):
                        continue
                    
                    logger.info(f"⚙️  Processing [{idx}/{len(all_events)}]: {ev.get('name', '')[:50]}")
                    
                    # Rate limit before fetch
                    self._rate_limit()
                    
                    # Fetch and parse with retries
                    results = self._fetch_tournament_results_with_retry(
                        ev.get("url", ""),
                        ev.get("bracket_url")
                    )
                    
                    if results is None:
                        error_msg = f"Failed to fetch results after {MAX_RETRIES} retries"
                        self.metrics.errors.append(f"{tournament_id}: {error_msg}")
                        self._update_scraper_metadata(tournament_id, "error", error_msg)
                        continue
                    
                    # Save to database
                    try:
                        is_new = self._save_tournament(
                            cursor, tournament_id, ev, results, fargo_cache
                        )
                        if is_new:
                            self.metrics.events_new += 1
                        else:
                            self.metrics.events_updated += 1
                        self.metrics.events_processed += 1
                        
                        self._update_scraper_metadata(tournament_id, "success")
                        conn.commit()
                        
                    except Exception as e:
                        error_msg = str(e)
                        logger.error(f"❌ Error saving {tournament_id}: {e}")
                        self.metrics.errors.append(f"{tournament_id}: {error_msg}")
                        self._update_scraper_metadata(tournament_id, "error", error_msg)
                        conn.rollback()
                
            finally:
                conn.close()
            
        except Exception as e:
            logger.error(f"❌ Critical error in scraper: {e}", exc_info=True)
            self.metrics.errors.append(f"Critical: {str(e)}")
        
        finally:
            self.metrics.end_time = datetime.now()
            self._save_scraper_run()
        
        # Log summary
        logger.info("=" * 60)
        logger.info("📊 SCRAPER RUN SUMMARY")
        logger.info("=" * 60)
        logger.info(f"   Duration: {self.metrics.to_dict()['duration_seconds']:.2f}s")
        logger.info(f"   Discovered: {self.metrics.events_discovered} events")
        logger.info(f"   Processed: {self.metrics.events_processed} events")
        logger.info(f"   New: {self.metrics.events_new}")
        logger.info(f"   Updated: {self.metrics.events_updated}")
        logger.info(f"   Future: {self.metrics.events_future}")
        logger.info(f"   Errors: {len(self.metrics.errors)}")
        logger.info(f"   Warnings: {len(self.metrics.warnings)}")
        logger.info("=" * 60)
        
        return self.metrics.to_dict()
    
    def _is_future_event(self, event: Dict) -> bool:
        """Check if an event is in the future."""
        try:
            end_date = event.get("end_date") or event.get("date")
            if not end_date:
                return False
            evt_date = datetime.fromisoformat(end_date).date() if isinstance(end_date, str) else end_date
            return evt_date >= datetime.now().date()
        except Exception:
            return False
    
    def _fetch_fargo_cache(self) -> Dict[str, float]:
        """Fetch Fargo ratings for all organizations."""
        fargo_cache = {}
        try:
            from api.services.fargo_client import fetch_fargo_ratings
            for org in ("WPBA", "WPA"):
                try:
                    self._rate_limit()
                    ratings = fetch_fargo_ratings(org, skip_cache=True)
                    for r in ratings:
                        name = (r.get("player_name") or r.get("name") or "").strip()
                        if name:
                            fargo_cache[name.lower()] = float(r.get("fargo_rating") or r.get("rating") or 0)
                    logger.info(f"✅ Loaded {len(ratings)} Fargo ratings for {org}")
                except Exception as e:
                    logger.warning(f"⚠️  Fargo fetch {org}: {e}")
                    self.metrics.warnings.append(f"Fargo {org}: {str(e)}")
        except Exception as e:
            logger.warning(f"⚠️  Fargo lookup disabled: {e}")
            self.metrics.warnings.append(f"Fargo: {str(e)}")
        return fargo_cache
    
    def _fetch_tournament_results_with_retry(
        self, event_url: str, bracket_url: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Fetch tournament results with retry logic."""
        from scrapers.tournament_bracket_parser import get_tournament_results
        
        for attempt in range(MAX_RETRIES):
            try:
                results = get_tournament_results(event_url, bracket_url)
                return results
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"⚠️  Fetch attempt {attempt + 1} failed: {e}, retrying...")
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"❌ All fetch attempts failed: {e}")
                    return None
        return None
    
    def _slug_tournament_id(self, name: str, year: int, association: str) -> str:
        """Generate a stable tournament_id from name, year, association."""
        slug = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")[:120]
        return f"{year}_{association}_{slug}" if slug else f"{year}_{association}_event"
    
    def _save_tournament(
        self, cursor, tournament_id: str, event: Dict, results: Dict, fargo_cache: Dict
    ) -> bool:
        """Save tournament and results to database. Returns True if new, False if updated."""
        # Check if tournament exists
        cursor.execute("SELECT tournament_id FROM tournament_history WHERE tournament_id = %s", (tournament_id,))
        is_new = cursor.fetchone() is None
        
        # Extract champion/runner-up from results
        champion = results.get("champion") or (results.get("placements") or [{}])[0].get("player_name")
        runner_up = results.get("runner_up")
        if not runner_up and len(results.get("placements") or []) >= 2:
            runner_up = results["placements"][1].get("player_name")
        final_score = results.get("final_score")
        
        # Determine status
        status = "upcoming" if self._is_future_event(event) else "completed"
        
        # Insert/update tournament
        cursor.execute("""
            INSERT INTO tournament_history
            (tournament_id, name, year, date, location, association, status, champion, runner_up, 
             final_score, source_url, bracket_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tournament_id) DO UPDATE SET
            name = EXCLUDED.name, date = EXCLUDED.date, location = EXCLUDED.location,
            status = EXCLUDED.status, champion = EXCLUDED.champion, runner_up = EXCLUDED.runner_up, 
            final_score = EXCLUDED.final_score, source_url = EXCLUDED.source_url, 
            bracket_url = EXCLUDED.bracket_url, updated_at = CURRENT_TIMESTAMP
        """, (
            tournament_id,
            event.get("name"),
            event.get("year"),
            event.get("date") or event.get("start_date"),
            event.get("location", "TBD"),
            event.get("association", "WPBA"),
            status,
            champion,
            runner_up,
            final_score,
            event.get("url"),
            event.get("bracket_url"),
        ))
        
        # Clear old results and matches
        cursor.execute("DELETE FROM tournament_history_matches WHERE tournament_id = %s", (tournament_id,))
        cursor.execute("DELETE FROM tournament_results WHERE tournament_id = %s", (tournament_id,))
        
        # Save placements
        for p in results.get("placements") or []:
            if not p.get("player_name"):
                continue
            name = p["player_name"].strip()[:255]
            place = p.get("place")
            fargo = fargo_cache.get(name.lower()) if fargo_cache else None
            cursor.execute("""
                INSERT INTO tournament_results (tournament_id, player_name, placement, points, fargo_rating_at_scrape)
                VALUES (%s, %s, %s, 0.0, %s)
                ON CONFLICT (tournament_id, player_name) DO UPDATE SET 
                placement = EXCLUDED.placement, fargo_rating_at_scrape = EXCLUDED.fargo_rating_at_scrape
            """, (tournament_id, name, place, fargo))
        
        # Save matches
        for i, m in enumerate(results.get("matches") or []):
            p1 = (m.get("operator_name") or "").strip()[:255] or "Unknown"
            p2 = (m.get("player2_name") or "").strip()[:255] or "Unknown"
            cursor.execute("""
                INSERT INTO tournament_history_matches
                (tournament_id, round_num, match_num, operator_name, player2_name, 
                 operator_score, player2_score, winner_name, match_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                tournament_id,
                m.get("round_num") or "",
                m.get("match_num") or i + 1,
                p1, p2,
                m.get("operator_score"),
                m.get("player2_score"),
                (m.get("winner_name") or "").strip()[:255] or None,
                event.get("date"),
            ))
        
        return is_new


def main():
    """Run enhanced scraper from command line."""
    import argparse
    import sys
    from pathlib import Path
    
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))
    
    from database import engine
    
    parser = argparse.ArgumentParser(description="Enhanced Tournament History Scraper")
    parser.add_argument("--wpba-only", action="store_true", help="Scrape WPBA only")
    parser.add_argument("--wpa-only", action="store_true", help="Scrape WPA only")
    parser.add_argument("--no-future", action="store_true", help="Skip future tournaments")
    parser.add_argument("--no-fargo", action="store_true", help="Skip Fargo rating attachment")
    parser.add_argument("--force", action="store_true", help="Force rescrape all tournaments")
    parser.add_argument("--limit", type=int, help="Limit number of tournaments to process")
    parser.add_argument("--rate-limit", type=float, default=RATE_LIMIT_DELAY, 
                       help=f"Delay between requests (default: {RATE_LIMIT_DELAY}s)")
    args = parser.parse_args()
    
    wpba = not args.wpa_only
    wpa = not args.wpba_only
    include_future = not args.no_future
    attach_fargo = not args.no_fargo
    
    scraper = EnhancedTournamentScraper(engine=engine, rate_limit_delay=args.rate_limit)
    
    result = scraper.scrape_tournaments(
        wpba=wpba,
        wpa=wpa,
        include_future=include_future,
        attach_fargo=attach_fargo,
        force_rescrape=args.force,
        limit=args.limit,
    )
    
    # Return 0 if no errors, 1 if errors occurred
    return 0 if result["error_count"] == 0 else 1


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    sys.exit(main())
