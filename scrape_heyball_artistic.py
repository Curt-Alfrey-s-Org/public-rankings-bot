#!/usr/bin/env python3
"""
One-time script to scrape and populate WPA Heyball Men, Heyball Women, and Artistic rankings.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scrapers.wpa_scraper import WPAScraper
from database import get_database_manager

def main():
    print("Initializing scrapers and database manager...")
    wpa_scraper = WPAScraper()
    db_manager = get_database_manager()
    
    results = {}
    
    # WPA Heyball Men
    print("\n=== Scraping WPA Heyball Men ===")
    try:
        rankings = wpa_scraper.scrape_rankings(division='Heyball_Men')
        if rankings:
            count = db_manager.save_wpa_rankings(rankings, ranking_type='WPA_Heyball_Men')
            results['heyball_men'] = {'success': True, 'count': count}
            print(f"✓ Saved {count} WPA Heyball Men rankings")
        else:
            results['heyball_men'] = {'success': False, 'error': 'No data returned'}
            print("✗ No rankings data returned")
    except Exception as e:
        results['heyball_men'] = {'success': False, 'error': str(e)}
        print(f"✗ Error: {e}")
    
    # WPA Heyball Women
    print("\n=== Scraping WPA Heyball Women ===")
    try:
        rankings = wpa_scraper.scrape_rankings(division='Heyball_Women')
        if rankings:
            count = db_manager.save_wpa_rankings(rankings, ranking_type='WPA_Heyball_Women')
            results['heyball_women'] = {'success': True, 'count': count}
            print(f"✓ Saved {count} WPA Heyball Women rankings")
        else:
            results['heyball_women'] = {'success': False, 'error': 'No data returned'}
            print("✗ No rankings data returned")
    except Exception as e:
        results['heyball_women'] = {'success': False, 'error': str(e)}
        print(f"✗ Error: {e}")
    
    # WPA Artistic
    print("\n=== Scraping WPA Artistic ===")
    try:
        rankings = wpa_scraper.scrape_rankings(division='Artistic')
        if rankings:
            count = db_manager.save_wpa_rankings(rankings, ranking_type='WPA_Artistic')
            results['artistic'] = {'success': True, 'count': count}
            print(f"✓ Saved {count} WPA Artistic rankings")
        else:
            results['artistic'] = {'success': False, 'error': 'No data returned'}
            print("✗ No rankings data returned")
    except Exception as e:
        results['artistic'] = {'success': False, 'error': str(e)}
        print(f"✗ Error: {e}")
    
    # Summary
    print("\n=== Summary ===")
    for system, result in results.items():
        status = "✓" if result['success'] else "✗"
        if result['success']:
            print(f"{status} {system}: {result['count']} rankings")
        else:
            print(f"{status} {system}: {result.get('error', 'Failed')}")
    
    return 0 if all(r['success'] for r in results.values()) else 1

if __name__ == '__main__':
    sys.exit(main())
