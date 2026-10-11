#!/usr/bin/env python3
"""
Master competitors Scraper Orchestrator

Runs all scrapers in parallel:
- Comprehensive tournament/venue scraper
- Bracket and match data scraper
- Player profile scraper

Aggregates all data into a unified reference archive.
"""

import subprocess
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class CompetitorsOrchestrator:
    def __init__(self, scripts_dir='/home/ansible/rankings-bot/scripts'):
        self.scripts_dir = Path(scripts_dir)
        self.output_dir = self.scripts_dir.parent / 'data' / 'competitors_archive'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = {}
    
    def run_scraper(self, script_name):
        """Run a single scraper script."""
        script_path = self.scripts_dir / script_name
        
        logger.info(f"Starting {script_name}...")
        
        try:
            result = subprocess.run(
                ['python3', str(script_path)],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                logger.info(f"✓ {script_name} completed successfully")
                self.results[script_name] = {
                    'status': 'success',
                    'stdout': result.stdout[-500:] if result.stdout else '',  # Last 500 chars
                }
            else:
                logger.error(f"✗ {script_name} failed")
                self.results[script_name] = {
                    'status': 'failed',
                    'error': result.stderr[-500:] if result.stderr else '',
                }
            
            return result.returncode
        
        except subprocess.TimeoutExpired:
            logger.error(f"✗ {script_name} timed out")
            self.results[script_name] = {'status': 'timeout'}
            return 1
        
        except Exception as e:
            logger.error(f"✗ Error running {script_name}: {e}")
            self.results[script_name] = {'status': 'error', 'error': str(e)}
            return 1
    
    def aggregate_data(self):
        """Aggregate all scraped data files."""
        logger.info("\nAggregating all scraped data...")
        
        archive_data = {
            'aggregated_at': datetime.now().isoformat(),
            'data_sources': {},
        }
        
        # Find all JSON files in archive directory
        json_files = list(self.output_dir.glob('*.json'))
        
        logger.info(f"Found {len(json_files)} data files to aggregate")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                source_name = json_file.stem
                archive_data['data_sources'][source_name] = {
                    'file': str(json_file),
                    'size_bytes': json_file.stat().st_size,
                }
                
                logger.info(f"  + {source_name} ({json_file.stat().st_size:,} bytes)")
            
            except Exception as e:
                logger.warning(f"  Failed to read {json_file}: {e}")
        
        return archive_data
    
    def create_summary_report(self):
        """Create summary report of scraping activity."""
        report = {
            'generated_at': datetime.now().isoformat(),
            'scraper_results': self.results,
            'archive_location': str(self.output_dir),
            'summary': {
                'successful_scrapers': sum(1 for r in self.results.values() if r.get('status') == 'success'),
                'failed_scrapers': sum(1 for r in self.results.values() if r.get('status') != 'success'),
            }
        }
        
        report_file = self.output_dir / f"scrape_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"\nScrape report saved to {report_file}")
        
        return report_file
    
    def run_all(self):
        """Run all scrapers in parallel."""
        logger.info("=" * 70)
        logger.info("Competitors Comprehensive Data Scraper")
        logger.info("=" * 70)
        
        scrapers = [
            'scrape_externalpool_comprehensive.py',
            'scrape_bracket_data.py',
            'scrape_player_profiles.py',
        ]
        
        logger.info(f"\nLaunching {len(scrapers)} scrapers in parallel...")
        logger.info("-" * 70)
        
        # Run scrapers in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self.run_scraper, scraper): scraper 
                for scraper in scrapers
            }
            
            for future in as_completed(futures):
                scraper_name = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Exception in {scraper_name}: {e}")
        
        logger.info("-" * 70)
        
        # Aggregate data
        aggregate_data = self.aggregate_data()
        
        # Create report
        report_file = self.create_summary_report()
        
        logger.info("\n" + "=" * 70)
        logger.info("SCRAPING COMPLETE")
        logger.info("=" * 70)
        
        # Print summary
        logger.info("\nResults Summary:")
        for scraper, result in self.results.items():
            status = result['status'].upper()
            symbol = '✓' if status == 'SUCCESS' else '✗'
            logger.info(f"  {symbol} {scraper}: {status}")
        
        logger.info(f"\nAll data archived at: {self.output_dir}")
        logger.info(f"Report: {report_file}")
        
        return self.output_dir

if __name__ == '__main__':
    orchestrator = CompetitorsOrchestrator()
    orchestrator.run_all()
