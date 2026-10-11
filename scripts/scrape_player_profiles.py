#!/usr/bin/env python3
"""
CP Player Profile Scraper

Extracts detailed player information:
- Player statistics (wins/losses, tournament appearances)
- Fargo ratings history
- Profile information
- Location/country data
- Tournament results
- Player rankings/standings

Designed for parallel processing of multiple players.
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

class PlayerScraper:
    def __init__(self, output_dir='data/cp_archive'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
        self.players_data = []
    
    def scrape_player(self, player_name):
        """Scrape individual player profile."""
        # Search for player
        search_url = f"https://www.digitalpool.com/search?query={player_name.replace(' ', '+')}"
        
        try:
            response = self.session.get(search_url, timeout=10)
            if response.status_code != 200:
                return None
        except Exception as e:
            logger.debug(f"Error searching for {player_name}: {e}")
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find player link
        player_link = soup.find('a', href=re.compile(r'/player/'))
        
        if not player_link:
            return None
        
        player_url = player_link.get('href', '')
        if not player_url.startswith('http'):
            player_url = f"https://www.digitalpool.com{player_url}"
        
        return self._scrape_player_profile(player_name, player_url)
    
    def _scrape_player_profile(self, player_name, player_url):
        """Scrape player profile page."""
        try:
            response = self.session.get(player_url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            logger.debug(f"Error fetching profile for {player_name}: {e}")
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        player_data = {
            'name': player_name,
            'url': player_url,
            'scraped_at': datetime.now().isoformat(),
            'location': self._extract_location(soup),
            'country': self._extract_country(soup),
            'statistics': self._extract_statistics(soup),
            'rating': self._extract_rating(soup),
            'tournaments': self._extract_tournament_history(soup),
            'bio': self._extract_bio(soup),
        }
        
        return player_data
    
    def _extract_location(self, soup):
        """Extract player location."""
        # Look for location in profile section
        for text in soup.stripped_strings:
            if any(state in text for state in ['California', 'Texas', 'Florida', 'New York']):
                return text
        return None
    
    def _extract_country(self, soup):
        """Extract country information."""
        # Look for country mentions
        text = soup.get_text()
        
        countries = ['United States', 'Canada', 'Great Britain', 'Australia', 'Japan',
                    'Germany', 'France', 'Spain', 'Taiwan', 'China', 'Philippines',
                    'Thailand', 'Vietnam', 'Bulgaria', 'Austria', 'Turkey', 'Russia',
                    'Argentina', 'Brazil', 'Mexico', 'Indonesia', 'Guam']
        
        for country in countries:
            if country.lower() in text.lower():
                return country
        
        return None
    
    def _extract_statistics(self, soup):
        """Extract player statistics."""
        stats = {}
        
        # Look for stat blocks
        for stat_div in soup.find_all('div', class_=re.compile(r'stat|score|record', re.I)):
            stat_text = stat_div.get_text(strip=True)
            
            # Parse common stat patterns
            if ':' in stat_text:
                key, value = stat_text.split(':', 1)
                stats[key.strip()] = value.strip()
        
        return stats if stats else None
    
    def _extract_rating(self, soup):
        """Extract Fargo rating."""
        for text in soup.stripped_strings:
            # Look for rating patterns (typically 400-800)
            match = re.search(r'(?:Rating|Fargo).*?(\d{3,4})', text)
            if match:
                return int(match.group(1))
        return None
    
    def _extract_tournament_history(self, soup):
        """Extract recent tournament appearances."""
        tournaments = []
        
        # Look for tournament tables
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            for row in rows[:10]:  # Get last 10
                cols = row.find_all('td')
                if len(cols) >= 2:
                    tournament_name = cols[0].get_text(strip=True)
                    result = cols[-1].get_text(strip=True)
                    
                    if tournament_name:
                        tournaments.append({
                            'tournament': tournament_name,
                            'result': result,
                        })
        
        return tournaments if tournaments else None
    
    def _extract_bio(self, soup):
        """Extract player bio/description."""
        # Look for bio section
        bio_div = soup.find('div', class_=re.compile(r'bio|about|description', re.I))
        
        if bio_div:
            return bio_div.get_text(strip=True)[:500]
        
        # Alternative: look for paragraphs
        paragraphs = soup.find_all('p')
        if paragraphs:
            return paragraphs[0].get_text(strip=True)[:500]
        
        return None
    
    def scrape_players_list(self, player_names):
        """Scrape multiple players in parallel."""
        logger.info(f"Scraping {len(player_names)} players...")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.scrape_player, name): name 
                for name in player_names
            }
            
            for idx, future in enumerate(as_completed(futures)):
                player_name = futures[future]
                try:
                    result = future.result()
                    if result:
                        self.players_data.append(result)
                        logger.info(f"  [{idx + 1}/{len(player_names)}] {player_name}")
                except Exception as e:
                    logger.debug(f"Error scraping {player_name}: {e}")
                
                # Rate limiting
                if (idx + 1) % 5 == 0:
                    time.sleep(2)
    
    def save_players(self):
        """Save player data to JSON."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        output_file = self.output_dir / f"player_profiles_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(self.players_data, f, indent=2)
        
        logger.info(f"Player data saved to {output_file}")
        logger.info(f"  Total profiles: {len(self.players_data)}")
        
        return output_file
    
    def run(self, player_names=None):
        """Run player scraper."""
        logger.info("=" * 70)
        logger.info("Starting CP Player Scraper")
        logger.info("=" * 70)
        
        if player_names is None:
            # Scrape some well-known WPBA players
            player_names = [
                'Kristina Tkach', 'Kelly Fisher', 'Pia Filler', 'Jasmin Ouschan',
                'Chezka Centeno', 'Chieh-Yu Chou', 'Yu Han', 'Sakura Muramatsu',
                'Monica Webb', 'Sofia Mast',
            ]
        
        self.scrape_players_list(player_names)
        self.save_players()
        
        logger.info("=" * 70)
        logger.info("Player Scrape Complete")
        logger.info("=" * 70)

if __name__ == '__main__':
    scraper = PlayerScraper()
    scraper.run()
