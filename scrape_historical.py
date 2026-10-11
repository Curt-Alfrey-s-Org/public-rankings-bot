#!/usr/bin/env python3
"""
Test script to scrape WPA historical rankings from previous-ranking page.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scrapers.wpa_scraper import WPAScraper
from database import get_database_manager

def main():
    print("=== WPA Historical Rankings Scraper ===\n")
    
    wpa_scraper = WPAScraper()
    
    # Scrape historical rankings
    print("Fetching historical rankings from https://wpapool.com/previous-ranking/")
    historical_data = wpa_scraper.scrape_historical_rankings()
    
    if not historical_data:
        print("❌ No historical data returned")
        return 1
    
    print(f"\n✓ Found {len(historical_data)} historical ranking snapshots\n")
    
    # Display what we found
    for ranking_type, snapshot_date, rankings in historical_data:
        print(f"  • {ranking_type}: {len(rankings)} players ({snapshot_date})")
    
    # Save to database
    print("\n=== Saving to Database ===\n")
    db_manager = get_database_manager()
    
    saved_counts = {}
    for ranking_type, snapshot_date, rankings in historical_data:
        if rankings:
            try:
                result = db_manager.save_wpa_rankings(
                    rankings, 
                    snapshot_date=snapshot_date,
                    ranking_type=ranking_type
                )
                saved_counts[f"{ranking_type}_{snapshot_date}"] = result
                print(f"✓ {ranking_type} ({snapshot_date}): {result}")
            except Exception as e:
                print(f"✗ {ranking_type} ({snapshot_date}): {e}")
    
    # Summary
    print("\n=== Summary ===")
    total_saved = sum(
        r.get('saved_count', 0) if isinstance(r, dict) else r
        for r in saved_counts.values()
    )
    print(f"Total snapshots: {len(historical_data)}")
    print(f"Total players saved: {total_saved}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
