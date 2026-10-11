#!/usr/bin/env python3
"""
Initialize Tournament History Data
Run this script to populate the database with tournament history (2022-2025)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from database import engine
from scrapers.tournament_history_scraper import TournamentHistoryScraper
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Initialize tournament history. Uses shared Postgres DB."""
    logger.info("🏆 Initializing Tournament History (2010-2025)...")
    scraper = TournamentHistoryScraper(engine=engine)
    
    # Initialize tables
    logger.info("📋 Creating tournament history tables...")
    scraper.init_tournament_tables()
    
    # Import tournament history
    logger.info("📥 Importing tournament history data...")
    scraper.import_tournament_history()
    
    # Get statistics
    stats = scraper.get_tournament_statistics()
    logger.info(f"📊 Tournament Statistics: {stats}")
    
    # Show 2025 tournaments
    tournaments_2025 = scraper.get_tournament_history(year=2025)
    logger.info(f"✅ 2025 Tournaments: {len(tournaments_2025)} found")
    for t in tournaments_2025:
        logger.info(f"   - {t['name']} ({t['association']})")
    
    logger.info("✅ Tournament history initialization complete!")
    logger.info("\nYou can now access tournament history via:")
    logger.info("  - GET /api/tournament-history/tournaments")
    logger.info("  - GET /api/tournament-history/tournaments/{tournament_id}")
    logger.info("  - GET /api/tournament-history/players/{player_name}/history")
    logger.info("  - GET /api/tournament-history/statistics")
    logger.info("  - GET /api/tournament-history/search?q=keyword")

if __name__ == "__main__":
    main()
