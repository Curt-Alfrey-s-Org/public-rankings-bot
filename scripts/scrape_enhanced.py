#!/usr/bin/env python3
"""
Enhanced CP Scraper with JavaScript handling and API endpoints

Uses direct API calls and better parsing for JavaScript-rendered content.
Falls back to static HTML parsing where possible.
"""

import requests
import json
import re
import logging
from datetime import datetime
from pathlib import Path
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class EnhancedCpScraper:
    def __init__(self, output_dir='data/cp_archive'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
    
    def scrape_tournaments_api(self):
        """Try to fetch tournaments via API endpoint."""
        logger.info("Attempting to scrape tournaments...")
        
        tournaments = []
        
        # Try multiple approaches
        urls_to_try = [
            'https://www.digitalpool.com/api/tournaments',
            'https://www.digitalpool.com/api/v1/tournaments',
            'https://api.digitalpool.com/tournaments',
        ]
        
        for url in urls_to_try:
            try:
                response = self.session.get(url, timeout=5)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        tournaments = data if isinstance(data, list) else data.get('tournaments', [])
                        logger.info(f"  ✓ Found tournaments via {url}")
                        return tournaments
                    except Exception as e:
                        logger.debug("Could not parse tournament API response from %s: %s", url, e)
            except Exception as e:
                logger.debug("Tournament API attempt failed for %s: %s", url, e)
        
        # Fallback: scrape specific known tournaments
        logger.info("  Using known tournament URLs...")
        
        known_tournaments = [
            {
                'name': '2026 WPBA Classic Players Championship',
                'url': '/tournaments/2026-wpba-classics-players-championship/bracket',
                'date': '2026-02-15',
                'location': 'Lauderhill, FL',
                'format': '9-ball',
            },
            {
                'name': '2025 WPBA Olhausen Colorado Classic',
                'url': '/tournaments/2025-wpba-olhausen-colorado-classic/bracket',
                'date': '2025-08-21',
                'location': 'Englewood, CO',
                'format': '9-ball',
            },
            {
                'name': '2025 WPBA Iron City Invitational VI',
                'url': '/tournaments/2025-olhausen-iron-city-invitational-vi/bracket',
                'date': '2025-02-TBD',
                'location': 'Birmingham, AL',
                'format': '9-ball',
            },
        ]
        
        return known_tournaments
    
    def scrape_bracket_html(self, bracket_url):
        """Scrape bracket data from HTML source."""
        full_url = f"https://www.digitalpool.com{bracket_url}" if not bracket_url.startswith('http') else bracket_url
        
        try:
            response = self.session.get(full_url, timeout=10)
            if response.status_code != 200:
                return None
            
            # Look for JavaScript data in HTML
            content = response.text
            
            # Try to extract JSON data from script tags
            import re
            matches = re.findall(r'<script[^>]*>.*?"brackets":\s*(\[.*?\])\s*</script>', content, re.DOTALL)
            
            if matches:
                try:
                    data = json.loads(matches[0])
                    logger.info(f"  ✓ Extracted JSON bracket data from {bracket_url}")
                    return data
                except Exception as e:
                    logger.debug("Could not parse bracket JSON from %s: %s", bracket_url, e)
            
            # Extract player data using regex patterns
            players = self._extract_players_from_html(content)
            matches = self._extract_matches_from_html(content)
            
            return {
                'url': full_url,
                'players': players,
                'matches': matches,
            }
        
        except Exception as e:
            logger.warning(f"Error scraping {bracket_url}: {e}")
            return None
    
    def _extract_players_from_html(self, html):
        """Extract players from HTML content."""
        players = []
        
        # Pattern 1: Player names with flag country codes
        # <img ... src="...flags/us.svg"> PlayerName
        player_pattern = r'(?:src=["\'].*?flags/([a-z]{2})(?:\.svg)?["\']|title=["\']([a-z]{2})["\']).*?([A-Z][a-zA-Z\s\-\.\']+)'
        
        for match in re.finditer(player_pattern, html, re.IGNORECASE | re.DOTALL):
            country_code = (match.group(1) or match.group(2) or '').lower()
            player_name = match.group(3).strip() if match.group(3) else ''
            
            if player_name and len(player_name) > 2:
                players.append({
                    'name': player_name,
                    'country_code': country_code,
                })
        
        # Pattern 2: Player names in bracketed format
        bracket_pattern = r'(\d+)\s*-\s*(\d+).*?([A-Z][a-zA-Z\s\-\.\']+)'
        
        for match in re.finditer(bracket_pattern, html):
            player_name = match.group(3).strip()
            if player_name and len(player_name) > 2 and player_name not in [p['name'] for p in players]:
                players.append({
                    'name': player_name,
                    'country_code': '',
                })
        
        return players
    
    def _extract_matches_from_html(self, html):
        """Extract match results from HTML."""
        matches = []
        
        # Pattern: score1 vs score2
        match_pattern = r'(\d+)\s*(?:vs|-|:)\s*(\d+)'
        
        for match in re.finditer(match_pattern, html):
            score1 = int(match.group(1))
            score2 = int(match.group(2))
            
            # Only include reasonable scores (0-11)
            if 0 <= score1 <= 11 and 0 <= score2 <= 11:
                matches.append({
                    'score1': score1,
                    'score2': score2,
                })
        
        return matches[:500]  # Limit to first 500
    
    def run(self):
        """Run enhanced scraper."""
        logger.info("=" * 70)
        logger.info("Enhanced ExternalPool Scraper with Direct Data Extraction")
        logger.info("=" * 70)
        
        # Scrape tournaments
        tournaments = self.scrape_tournaments_api()
        logger.info(f"Found {len(tournaments)} tournaments")
        
        # Scrape bracket data for known tournaments
        bracket_data = []
        for tournament in tournaments[:5]:  # First 5
            url = tournament.get('url', '')
            name = tournament.get('name', '')
            
            if url:
                logger.info(f"Scraping brackets for {name}...")
                data = self.scrape_bracket_html(url)
                if data:
                    data['tournament_name'] = name
                    bracket_data.append(data)
                    logger.info(f"  Players: {len(data.get('players', []))}, Matches: {len(data.get('matches', []))}")
                
                time.sleep(1)  # Rate limit
        
        # Save data
        self._save_comprehensive_data(tournaments, bracket_data)
        
        logger.info("=" * 70)
        logger.info("Scraping Complete")
        logger.info("=" * 70)
    
    def _save_comprehensive_data(self, tournaments, brackets):
        """Save all data to archive."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Summary stats
        total_players = sum(len(b.get('players', [])) for b in brackets)
        total_matches = sum(len(b.get('matches', [])) for b in brackets)
        
        archive = {
            'scraped_at': datetime.now().isoformat(),
            'tournaments_count': len(tournaments),
            'brackets_count': len(brackets),
            'total_players_unique': total_players,
            'total_matches': total_matches,
            'tournaments': tournaments,
            'brackets': brackets,
        }
        
        # Save archive
        archive_file = self.output_dir / f"externalpool_full_archive_{timestamp}.json"
        with open(archive_file, 'w') as f:
            json.dump(archive, f, indent=2)
        
        logger.info(f"\nArchive saved: {archive_file}")
        logger.info(f"  Tournaments: {len(tournaments)}")
        logger.info(f"  Tournaments with bracket data: {len(brackets)}")
        logger.info(f"  Total unique players: {total_players}")
        logger.info(f"  Total matches: {total_matches}")
        
        return archive_file

if __name__ == '__main__':
    scraper = EnhancedCpScraper()
    scraper.run()
