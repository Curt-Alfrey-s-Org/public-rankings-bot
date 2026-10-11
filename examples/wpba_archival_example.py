#!/usr/bin/env python3
"""
Example: Migrating WPBA Scraper to Use Standard Archival

This script demonstrates how to update an existing scraper to use
the standardized archive_utils module.
"""

import logging
from scrapers.wpba_scraper import WPBAScraper
from scrapers.archive_utils import DataArchiver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def scrape_and_archive_wpba():
    """
    Example of scraping WPBA data and archiving with standard format
    """
    logger.info("="*80)
    logger.info("WPBA Scraper with Standardized Archival")
    logger.info("="*80)
    
    # Initialize scraper
    scraper = WPBAScraper()
    
    # Initialize archiver
    archiver = DataArchiver('wpba')
    
    # Create README if it doesn't exist
    readme_path = archiver.archive_dir / 'README.md'
    if not readme_path.exists():
        logger.info("Creating archive README...")
        archiver.create_readme(
            description="""
WPBA (Women's Professional Billiard Association) Rankings Archive

Contains historical and current rankings data for women's professional pool players.
Data is scraped from the official WPBA website and includes player rankings, points,
and additional tournament information.
""".strip(),
            data_sources=[
                'https://wpba.com/rankings',
                'https://wpba.com/tour-info/rankings'
            ],
            file_types={
                'wpba_rankings_*.json': 'Current WPBA rankings with player details',
                'wpba_summary_*.json': 'Summary statistics and metadata',
                'wpba_historical_*.json': 'Historical rankings data (if available)'
            },
            usage_examples="""
### Load Current Rankings
```python
import json

with open('data/wpba_archive/wpba_rankings_YYYYMMDD_HHMMSS.json') as f:
    archive = json.load(f)
    rankings = archive['data']
    
    # Get top 10 players
    top_10 = sorted(rankings, key=lambda x: x['rank'])[:10]
    
    for player in top_10:
        print(f"{player['rank']}. {player['player_name']} - {player['points']} pts")
```

### Compare Archives
```python
from scrapers.archive_utils import DataArchiver

archiver = DataArchiver('wpba')
archives = archiver.list_archives()

# Compare two most recent
if len(archives) >= 2:
    latest = archives[0]
    previous = archives[1]
    
    print(f"Latest: {latest['total_records']} players")
    print(f"Previous: {previous['total_records']} players")
```
"""
        )
    
    try:
        # Scrape current rankings
        logger.info("Scraping WPBA rankings...")
        rankings = scraper.scrape_rankings()
        
        if not rankings:
            logger.error("No rankings data scraped")
            return
        
        logger.info(f"Scraped {len(rankings)} player rankings")
        
        # Calculate additional statistics
        statistics = {
            'total_players': len(rankings),
            'players_with_points': sum(1 for p in rankings if p.get('points', 0) > 0),
            'countries': len(set(p.get('country') for p in rankings if p.get('country'))),
            'top_player': rankings[0].get('player_name') if rankings else None,
            'top_points': rankings[0].get('points') if rankings else 0
        }
        
        # Archive rankings
        logger.info("Archiving rankings data...")
        rankings_file = archiver.archive_data(
            data=rankings,
            metadata={
                'data_source': 'https://wpba.com/rankings',
                'ranking_system': 'WPBA_Women',
                'scraper_version': '1.0'
            },
            statistics=statistics,
            filename_suffix='rankings'
        )
        
        logger.info(f"✓ Rankings archived: {rankings_file}")
        
        # Create summary archive
        logger.info("Creating summary archive...")
        summary_data = {
            'ranking_systems': ['WPBA_Women'],
            'total_players': len(rankings),
            'archive_created': archiver.iso_timestamp,
            'top_10_players': [
                {
                    'rank': p.get('rank'),
                    'name': p.get('player_name'),
                    'points': p.get('points')
                }
                for p in rankings[:10]
            ]
        }
        
        summary_file = archiver.archive_summary(
            summary_data=summary_data,
            filename_suffix='summary'
        )
        
        logger.info(f"✓ Summary archived: {summary_file}")
        
        # Print summary
        print("\n" + "="*80)
        print("Archive Complete")
        print("="*80)
        print(f"Rankings File: {rankings_file.name}")
        print(f"Summary File:  {summary_file.name}")
        print(f"Total Players: {len(rankings)}")
        print(f"Archive Dir:   {archiver.archive_dir}")
        print("="*80)
        
        return {
            'success': True,
            'rankings_file': str(rankings_file),
            'summary_file': str(summary_file),
            'total_records': len(rankings)
        }
        
    except Exception as e:
        logger.error(f"Error during scraping/archival: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


def list_wpba_archives():
    """List all WPBA archives"""
    archiver = DataArchiver('wpba')
    archives = archiver.list_archives()
    
    print("\n" + "="*80)
    print("WPBA Archives")
    print("="*80)
    
    if not archives:
        print("No archives found")
        return
    
    for archive in archives:
        size_kb = archive['size_bytes'] / 1024
        print(f"\n{archive['filename']}")
        print(f"  Timestamp: {archive['timestamp']}")
        print(f"  Records:   {archive['total_records']}")
        print(f"  Size:      {size_kb:.1f} KB")
    
    print("\n" + "="*80)


def load_latest_wpba():
    """Load and display latest WPBA archive"""
    archiver = DataArchiver('wpba')
    
    latest = archiver.load_latest_archive('rankings')
    
    if not latest:
        print("No archives found")
        return
    
    metadata = latest['metadata']
    statistics = latest['statistics']
    data = latest['data']
    
    print("\n" + "="*80)
    print("Latest WPBA Archive")
    print("="*80)
    print(f"Timestamp: {metadata['archive_timestamp']}")
    print(f"Source:    {metadata.get('data_source', 'N/A')}")
    print(f"Records:   {metadata['total_records']}")
    print("\nTop 10 Players:")
    print("-"*80)
    
    for i, player in enumerate(data[:10], 1):
        name = player.get('player_name', 'Unknown')
        rank = player.get('rank', i)
        points = player.get('points', 0)
        print(f"{rank:3}. {name:40} {points:8.1f} pts")
    
    print("="*80)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'scrape':
            result = scrape_and_archive_wpba()
            sys.exit(0 if result.get('success') else 1)
        
        elif command == 'list':
            list_wpba_archives()
        
        elif command == 'latest':
            load_latest_wpba()
        
        else:
            print(f"Unknown command: {command}")
            print("Usage: python examples/wpba_archival_example.py [scrape|list|latest]")
            sys.exit(1)
    else:
        # Default: scrape and archive
        result = scrape_and_archive_wpba()
        sys.exit(0 if result.get('success') else 1)
