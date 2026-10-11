#!/usr/bin/env python3
"""
ExternalPool Bracket & Match Data Scraper

Specializes in extracting:
- Player names and countries from bracket flags
- Match results and scores  
- Player rankings/seeding
- Match timestamps
- Final standings

Can run in parallel for multiple tournaments.
"""

import requests
import json
import re
import logging
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class BracketScraper:
    def __init__(self, output_dir='data/externalpool_archive'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
        self.brackets_data = []
        
        # Country code mappings
        self.flag_codes = {
            'us': 'United States', 'gb': 'Great Britain', 'ca': 'Canada',
            'au': 'Australia', 'jp': 'Japan', 'de': 'Germany', 'fr': 'France',
            'es': 'Spain', 'it': 'Italy', 'ru': 'Russia', 'cn': 'China',
            'tw': 'Taiwan', 'ph': 'Philippines', 'th': 'Thailand',
            'in': 'India', 'br': 'Brazil', 'mx': 'Mexico', 'ar': 'Argentina',
            'bg': 'Bulgaria', 'at': 'Austria', 'tr': 'Turkey', 'vn': 'Vietnam',
            'id': 'Indonesia', 'gu': 'Guam',
        }
    
    def scrape_bracket(self, tournament_name, tournament_url):
        """Scrape a single bracket."""
        bracket_url = f"{tournament_url}/bracket" if not tournament_url.endswith('/bracket') else tournament_url
        full_url = f"https://www.digitalpool.com{bracket_url}" if not bracket_url.startswith('http') else bracket_url
        
        logger.info(f"Scraping bracket: {tournament_name}")
        
        try:
            response = self.session.get(full_url, timeout=15)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch bracket {tournament_name}: {e}")
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        bracket_data = {
            'tournament_name': tournament_name,
            'url': full_url,
            'scraped_at': datetime.now().isoformat(),
            'players': self._extract_players(soup),
            'matches': self._extract_matches(soup),
            'standings': self._extract_standings(soup),
        }
        
        logger.info(f"  Players: {len(bracket_data['players'])}, Matches: {len(bracket_data['matches'])}")
        
        return bracket_data
    
    def _extract_players(self, soup):
        """Extract all players from bracket with country flags."""
        players = {}
        
        # Pattern 1: SVG flag with country code (common in ExternalPool)
        for flag_elem in soup.find_all(re.compile(r'svg|img'), {'title': re.compile(r'^[a-z]{2}$', re.I)}):
            country_code = flag_elem.get('title', '').lower()
            # Find adjacent player name
            parent = flag_elem.find_parent()
            if parent:
                player_name = parent.get_text(strip=True)
                if player_name:
                    players[player_name] = {
                        'name': player_name,
                        'country_code': country_code,
                        'country': self.flag_codes.get(country_code, ''),
                    }
        
        # Pattern 2: Img flags with src path
        for img in soup.find_all('img', src=re.compile(r'(-|/)([a-z]{2})(\.|/)', re.I)):
            src = img.get('src', '')
            match = re.search(r'(-|/)([a-z]{2})(\.|/)', src, re.I)
            if match:
                country_code = match.group(2).lower()
                parent = img.find_parent()
                if parent:
                    player_name = parent.get_text(strip=True)
                    if player_name and player_name not in players:
                        players[player_name] = {
                            'name': player_name,
                            'country_code': country_code,
                            'country': self.flag_codes.get(country_code, ''),
                        }
        
        # Pattern 3: Extract all player names from bracket (as fallback)
        for table_row in soup.find_all('tr'):
            cols = table_row.find_all('td')
            for col in cols:
                text = col.get_text(strip=True)
                # Check for player name patterns (usually capitalized)
                if text and len(text) > 3 and text[0].isupper():
                    if text not in players and len(text.split()) <= 3:  # Likely a name
                        if text not in ['Table', 'COMPLETED', 'Round']:  # Skip headers
                            players[text] = {'name': text, 'country_code': None}
        
        return list(players.values())
    
    def _extract_matches(self, soup):
        """Extract match results."""
        matches = []
        
        # Find all match-like rows/divs
        for match_elem in soup.find_all(re.compile(r'match|round|game|table'), recursive=True):
            text = match_elem.get_text(strip=True)
            
            # Look for score patterns
            if re.search(r'\d+-\d+', text):  # Simple score like 8-3
                match_data = self._parse_match_text(text)
                if match_data:
                    matches.append(match_data)
        
        return matches[:500]  # Limit to 500 matches
    
    def _parse_match_text(self, text):
        """Parse match text to extract components."""
        # Match pattern: "Operator 8 vs 3 Player2" or similar
        score_match = re.search(r'(\d+)\s*(?:vs|-|L to)\s*(\d+)', text)
        
        if score_match:
            return {
                'score1': int(score_match.group(1)),
                'score2': int(score_match.group(2)),
                'text': text[:200],  # First 200 chars for context
            }
        
        return None
    
    def _extract_standings(self, soup):
        """Extract final standings if available."""
        standings = []
        
        # Look for tables with rankings
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            if len(rows) > 2:
                # Assume first row is headers
                for idx, row in enumerate(rows[1:6]):  # Get top 5
                    cols = row.find_all('td')
                    if cols:
                        standings.append({
                            'position': idx + 1,
                            'data': [col.get_text(strip=True) for col in cols],
                        })
        
        return standings
    
    def scrape_wpa_tournaments(self):
        """Scrape WPBA and WPA recent tournaments."""
        logger.info("Fetching WPBA tournament list...")
        
        tournaments_to_scrape = [
            ('2026 WPBA Classic', '/tournaments/2026-wpba-classics-players-championship'),
            ('2025 WPBA Colorado', '/tournaments/2025-wpba-olhausen-colorado-classic'),
            ('2025 Iron City', '/tournaments/2025-olhausen-iron-city-invitational-vi'),
        ]
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self.scrape_bracket, name, url): name 
                for name, url in tournaments_to_scrape
            }
            
            for future in as_completed(futures):
                tournament_name = futures[future]
                try:
                    result = future.result()
                    if result:
                        self.brackets_data.append(result)
                except Exception as e:
                    logger.error(f"Error scraping {tournament_name}: {e}")
                
                time.sleep(1)  # Rate limiting between requests
    
    def save_brackets(self):
        """Save bracket data to JSON."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        output_file = self.output_dir / f"bracket_data_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(self.brackets_data, f, indent=2)
        
        logger.info(f"Bracket data saved to {output_file}")
        
        # Summary stats
        total_players = sum(len(b['players']) for b in self.brackets_data)
        total_matches = sum(len(b['matches']) for b in self.brackets_data)
        
        logger.info(f"  Tournaments: {len(self.brackets_data)}")
        logger.info(f"  Total Players: {total_players}")
        logger.info(f"  Total Matches: {total_matches}")
        
        return output_file
    
    def run(self):
        """Run bracket scraper."""
        logger.info("=" * 70)
        logger.info("Starting ExternalPool Bracket Scraper")
        logger.info("=" * 70)
        
        self.scrape_wpa_tournaments()
        self.save_brackets()
        
        logger.info("=" * 70)
        logger.info("Bracket Scrape Complete")
        logger.info("=" * 70)

if __name__ == '__main__':
    scraper = BracketScraper()
    scraper.run()
