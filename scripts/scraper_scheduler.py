#!/usr/bin/env python3
"""
Scraper Scheduler - Stagger different scrapers throughout the day
to avoid spiking traffic on target servers and prevent IP bans.

Schedule:
- 02:00 - WPBA Rankings (niche scraper)
- 06:30 - WPA Rankings (main scraper)
- 11:00 - Fargo Ratings (supplementary data)
- 15:30 - Tournament History (core data)
- 20:00 - Heyball/Artistic (niche data)
"""

import os
import sys
import logging
import subprocess
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ansible/rankings-bot/logs/scraper_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Scheduled scraper jobs
SCRAPER_SCHEDULE = [
    {
        'name': 'WPBA Rankings',
        'hour': 2,
        'minute': 0,
        'command': 'python3 -m scrapers.wpba_scraper',
        'description': 'Scrape WPBA rankings (niche, less frequent)'
    },
    {
        'name': 'WPA Rankings',
        'hour': 6,
        'minute': 30,
        'command': 'python3 -m scrapers.wpa_scraper',
        'description': 'Scrape main WPA rankings'
    },
    {
        'name': 'Tournament History',
        'hour': 11,
        'minute': 0,
        'command': 'python3 -m scrapers.tournament_scraper_improved --rate-limit 10',
        'description': 'Scrape tournament history (core data, 10s delay)',
        'cwd': '/home/ansible/rankings-bot'
    },
    {
        'name': 'Fargo Ratings',
        'hour': 15,
        'minute': 30,
        'command': 'python3 -m scrapers.fairmatch_scraper',
        'description': 'Scrape Fargo ratings (supplementary)'
    },
    {
        'name': 'Heyball/Artistic',
        'hour': 20,
        'minute': 0,
        'command': 'python3 api/services/events_scraper.py heyball artistic',
        'description': 'Scrape Heyball and Artistic divisions (niche)',
        'cwd': '/home/ansible/rankings-bot'
    },
]

def generate_crontab():
    """Generate crontab entries for the scraper schedule."""
    cron_entries = []
    cron_entries.append('# Scraper Schedule - Staggered to prevent IP ban')
    cron_entries.append('# Last updated: ' + datetime.now().isoformat())
    cron_entries.append('')
    
    for job in SCRAPER_SCHEDULE:
        cwd = job.get('cwd', '/home/ansible/rankings-bot')
        comment = f"# {job['description']}"
        cron_line = f"{job['minute']} {job['hour']} * * * cd {cwd} && {job['command']} >> /home/ansible/rankings-bot/logs/scraper_{job['name'].lower().replace(' ', '_')}.log 2>&1"
        cron_entries.append(comment)
        cron_entries.append(cron_line)
        cron_entries.append('')
    
    return '\n'.join(cron_entries)

def install_cron_schedule():
    """Install the scraper schedule into crontab."""
    try:
        # Create logs directory
        logs_dir = Path('/home/ansible/rankings-bot/logs')
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate crontab entries
        cron_content = generate_crontab()
        
        # Write to temporary file
        temp_cron = '/tmp/scraper_crontab.txt'
        with open(temp_cron, 'w') as f:
            f.write(cron_content)
        
        logger.info(f"Generated crontab schedule at {temp_cron}")
        logger.info("Current schedule:")
        logger.info(cron_content)
        
        # To install, user must run: crontab /tmp/scraper_crontab.txt
        logger.info("\nTo install this schedule, run: crontab /tmp/scraper_crontab.txt")
        logger.info("To view current crontab, run: crontab -l")
        
        return temp_cron
    except Exception as e:
        logger.error(f"Failed to generate crontab: {e}")
        return None

def show_schedule():
    """Display the scraper schedule."""
    print("\n" + "="*70)
    print("SCRAPER SCHEDULE - Staggered Throughout Day")
    print("="*70)
    for job in SCRAPER_SCHEDULE:
        time_str = f"{job['hour']:02d}:{job['minute']:02d}"
        print(f"\n{time_str} - {job['name']}")
        print(f"  Description: {job['description']}")
        print(f"  Command: {job['command']}")
    print("\n" + "="*70)
    print("\nRationale: Distributing scrapes 4+ hours apart prevents IP ban by:")
    print("1. Avoiding traffic spikes from single IP")
    print("2. Looking like organic usage patterns")
    print("3. Respecting target servers' resources")
    print("4. Giving time for data changes between scrapes")
    print("="*70 + "\n")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'install':
            install_cron_schedule()
        elif sys.argv[1] == 'show':
            show_schedule()
        else:
            print(f"Usage: {sys.argv[0]} [show|install]")
    else:
        show_schedule()
        print("\nTo install the schedule, run: python3 scripts/scraper_scheduler.py install\n")
