#!/usr/bin/env python3
"""
Scrape and save rankings to database
Runs all rankings scrapers and saves results to PostgreSQL
"""

import sys
import logging
from datetime import date
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.multi_type_rankings_scraper import MultiTypeRankingsScraper
from database.postgres_manager import PostgresManager as DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Scrape and save all rankings"""
    logger.info("Starting rankings scrape and save")
    
    # Initialize scraper and database
    scraper = MultiTypeRankingsScraper()
    db = DatabaseManager()
    
    try:
        # Scrape all rankings
        logger.info("Scraping rankings...")
        all_rankings = scraper.scrape_all_rankings()
        
        # Deduplicate
        logger.info("Deduplicating rankings...")
        deduped, report = scraper.deduplicate_rankings(all_rankings)
        
        logger.info("Deduplication complete: %d total, %d duplicates removed", 
                   report['total_after'], report['duplicates_removed'])
        
        # Save to database
        today = date.today()
        total_saved = 0
        
        for ranking_type, rankings in deduped.items():
            if not rankings:
                logger.warning("No rankings for %s, skipping", ranking_type)
                continue
            
            logger.info("Saving %d %s rankings...", len(rankings), ranking_type)
            
            # Map ranking_type to system name expected by db_manager
            system_map = {
                'WPBA_Women': 'wpba-women',
                'WPA_Men': 'wpa-men',
                'WPA_Women': 'wpa-women'
            }
            system = system_map.get(ranking_type, ranking_type.lower().replace('_', '-'))
            
            db.save_rankings(rankings, system, snapshot_date=today)
            total_saved += len(rankings)
            logger.info("Saved %d %s rankings", len(rankings), ranking_type)
        
        logger.info("Successfully saved %d total rankings to database", total_saved)
        
        # Print summary
        print("\n=== Rankings Scrape Complete ===")
        print(f"Total rankings scraped: {report['total_before']}")
        print(f"Duplicates removed: {report['duplicates_removed']}")
        print(f"Total saved to database: {total_saved}")
        print(f"\nRankings by type:")
        for ranking_type, rankings in deduped.items():
            print(f"  {ranking_type}: {len(rankings)} players")
        
    except Exception as e:
        logger.error("Failed to scrape and save rankings: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    main()
