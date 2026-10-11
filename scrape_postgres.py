#!/usr/bin/env python3
"""
Scrape and save rankings directly to PostgreSQL
"""

import os
import sys
import logging
from datetime import date
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.multi_type_rankings_scraper import MultiTypeRankingsScraper
import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get PostgreSQL connection"""
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return psycopg2.connect(database_url)
    
    # Fallback to individual env vars
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'postgres'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB', 'rankingsbot'),
        user=os.getenv('POSTGRES_USER', 'rankingsbot_user'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )


def save_rankings_to_postgres(rankings, ranking_system, snapshot_date):
    """
    Save rankings to PostgreSQL
    
    Args:
        rankings: List of ranking dicts with keys: name, rank, points, country
        ranking_system: System name (WPBA_Women, WPA_Men, WPA_Women)
        snapshot_date: Date of snapshot
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    saved_count = 0
    error_count = 0
    
    try:
        for ranking in rankings:
            try:
                cursor.execute("""
                    INSERT INTO rankings 
                    (player_name, ranking_system, rank, points, country, snapshot_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (player_name, ranking_system, snapshot_date) 
                    DO UPDATE SET 
                        rank = EXCLUDED.rank,
                        points = EXCLUDED.points,
                        country = EXCLUDED.country
                """, (
                    ranking['name'],
                    ranking_system,
                    ranking['rank'],
                    ranking.get('points', 0),
                    ranking.get('country', ''),
                    snapshot_date
                ))
                saved_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"Error saving ranking for {ranking.get('name')}: {e}")
        
        conn.commit()
        logger.info(f"Saved {saved_count} {ranking_system} rankings (with {error_count} errors)")
        
    except Exception as e:
        logger.error(f"Database error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    
    return saved_count


def main():
    """Scrape and save all rankings"""
    logger.info("Starting rankings scrape and save to PostgreSQL")
    
    # Initialize scraper
    scraper = MultiTypeRankingsScraper()
    
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
            
            # Use the ranking_type as-is (WPBA_Women, WPA_Men, WPA_Women)
            saved = save_rankings_to_postgres(rankings, ranking_type, today)
            total_saved += saved
            logger.info("Saved %d %s rankings", saved, ranking_type)
        
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


if __name__ == '__main__':
    main()
