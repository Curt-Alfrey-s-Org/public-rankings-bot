#!/usr/bin/env python3
"""
Comprehensive External Pool (digitalpool.com) Data Scraper

Extracts:
- Tournament metadata (date, location, prize pool, format)
- Player profiles and bios
- Country/nationality data from bracket flags
- Match results and bracket data
- Venue information
- Historical data for reference

Stores all data as JSON for app reference and future enrichment.
"""

import requests
import json
import time
import os
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class CpScraper:
    def __init__(self, output_dir='data/cp_archive'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
        self.tournaments = []
        self.players = {}
        self.venues = {}
        self.country_mapping = {}
        
    def fetch_page(self, url, max_retries=3):
        """Fetch page with retry logic."""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for {url}: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error(f"Failed to fetch {url} after {max_retries} attempts")
        return None
    
    def scrape_tournaments_list(self):
        """Scrape tournament listings from CP (external pool)."""
        logger.info("Scraping tournament listings...")
        url = "https://www.digitalpool.com/tournaments"
        
        response = self.fetch_page(url)
        if not response:
            return
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all tournament cards
        tournament_cards = soup.find_all('div', class_=re.compile(r'tournament|event', re.I))
        
        logger.info(f"Found {len(tournament_cards)} tournament elements")
        
        # Extract tournament data from visible text
        tournament_links = soup.find_all('a', href=re.compile(r'/tournaments/'))
        
        for link in tournament_links:
            try:
                tournament_url = link.get('href', '')
                tournament_name = link.get_text(strip=True)
                
                if tournament_name and tournament_url:
                    self.tournaments.append({
                        'name': tournament_name,
                        'url': tournament_url,
                        'scraped_at': datetime.now().isoformat()
                    })
                    logger.info(f"  + {tournament_name}")
            except Exception as e:
                logger.debug(f"Error parsing tournament link: {e}")
        
        logger.info(f"Total tournaments found: {len(self.tournaments)}")
        return self.tournaments
    
    def scrape_tournament_details(self, tournament_url):
        """Scrape detailed tournament information."""
        try:
            full_url = f"https://www.digitalpool.com{tournament_url}" if not tournament_url.startswith('http') else tournament_url
            response = self.fetch_page(full_url)
            
            if not response:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            tournament_data = {
                'url': full_url,
                'scraped_at': datetime.now().isoformat(),
                'title': soup.find('h1', {}).get_text(strip=True) if soup.find('h1') else '',
                'date': self._extract_date(soup),
                'location': self._extract_location(soup),
                'director': self._extract_director(soup),
                'format': self._extract_format(soup),
                'prize_pool': self._extract_prize_pool(soup),
                'players_count': self._extract_player_count(soup),
                'description': self._extract_description(soup),
                'status': self._extract_status(soup),
            }
            
            return tournament_data
        except Exception as e:
            logger.error(f"Error scraping tournament details from {tournament_url}: {e}")
            return None
    
    def _extract_date(self, soup):
        """Extract tournament date."""
        for text in soup.stripped_strings:
            if any(month in text for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                                                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']):
                return text
        return None
    
    def _extract_location(self, soup):
        """Extract tournament location."""
        location_patterns = [
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})',  # City, State
            r'([A-Z][a-z]+),\s*([A-Z][a-z]+)',  # City, Country
        ]
        
        for text in soup.stripped_strings:
            for pattern in location_patterns:
                match = re.search(pattern, text)
                if match:
                    return text
        return None
    
    def _extract_director(self, soup):
        """Extract tournament director."""
        for text in soup.stripped_strings:
            if text.startswith('Director:') or text.startswith('Tournament Director:'):
                return text.replace('Director:', '').replace('Tournament Director:', '').strip()
        return None
    
    def _extract_format(self, soup):
        """Extract tournament format (9-ball, 8-ball, etc)."""
        text = soup.get_text()
        formats = ['9-ball', '8-ball', '10-ball', 'one pocket', 'straight pool']
        for fmt in formats:
            if fmt.lower() in text.lower():
                return fmt
        return None
    
    def _extract_prize_pool(self, soup):
        """Extract prize pool amount."""
        text = soup.get_text()
        prize_pattern = r'\$[\d,]+(?:\s*-\s*\$[\d,]+)?'
        match = re.search(prize_pattern, text)
        if match:
            return match.group(0)
        return None
    
    def _extract_player_count(self, soup):
        """Extract player count."""
        for text in soup.stripped_strings:
            if 'Players' in text:
                match = re.search(r'(\d+)\s*Players', text)
                if match:
                    return int(match.group(1))
        return None
    
    def _extract_description(self, soup):
        """Extract tournament description/rules."""
        desc_divs = soup.find_all('div', class_=re.compile(r'description|rules|format', re.I))
        if desc_divs:
            return desc_divs[0].get_text(strip=True)[:500]  # First 500 chars
        return None
    
    def _extract_status(self, soup):
        """Extract tournament status (upcoming, in progress, completed)."""
        text = soup.get_text().lower()
        if 'completed' in text:
            return 'completed'
        elif 'in progress' in text or 'live' in text:
            return 'in_progress'
        elif 'upcoming' in text:
            return 'upcoming'
        return 'unknown'
    
    def scrape_bracket_data(self, tournament_url):
        """Scrape bracket and participant data with country flags."""
        try:
            bracket_url = f"{tournament_url}/bracket" if not tournament_url.endswith('/bracket') else tournament_url
            full_url = f"https://www.digitalpool.com{bracket_url}" if not bracket_url.startswith('http') else bracket_url
            
            response = self.fetch_page(full_url)
            if not response:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            players_data = []
            
            # Extract player data with country codes from flag SVGs/images
            player_elements = soup.find_all(re.compile(r'.*player.*'), recursive=True)
            
            for elem in player_elements:
                player_info = self._extract_player_info(elem)
                if player_info:
                    players_data.append(player_info)
            
            return {
                'url': full_url,
                'scraped_at': datetime.now().isoformat(),
                'players': players_data,
                'matches': self._extract_match_data(soup),
            }
        except Exception as e:
            logger.error(f"Error scraping bracket from {tournament_url}: {e}")
            return None
    
    def _extract_player_info(self, elem):
        """Extract player information including country flag."""
        try:
            player_text = elem.get_text(strip=True)
            
            # Look for flag country codes (e.g., title="us" or data-country="us")
            country_code = None
            
            # Check for SVG flags
            flag_svgs = elem.find_all('svg', title=re.compile(r'^[a-z]{2}$', re.I))
            if flag_svgs:
                country_code = flag_svgs[0].get('title', '').upper()
            
            # Check for img flags
            flag_imgs = elem.find_all('img', src=re.compile(r'flags|countries', re.I))
            for img in flag_imgs:
                src = img.get('src', '')
                match = re.search(r'flags/([a-z]{2})', src)
                if match:
                    country_code = match.group(1).upper()
                    break
            
            # Check for data attributes
            country = elem.get('data-country') or elem.get('data-flag')
            
            if player_text and (country_code or country):
                return {
                    'name': player_text,
                    'country_code': country_code or country,
                    'source': 'bracket',
                }
            
            return None
        except Exception as e:
            logger.debug(f"Error extracting player info: {e}")
            return None
    
    def _extract_match_data(self, soup):
        """Extract match results and scores."""
        matches = []
        match_rows = soup.find_all(re.compile(r'match|round'))
        
        for row in match_rows[:100]:  # Limit to first 100 matches
            text = row.get_text(strip=True)
            if any(score in text for score in ['8-', '9-', '10-']):  # Score pattern
                matches.append({'data': text})
        
        return matches
    
    def scrape_players_directory(self):
        """Scrape player directory/profiles if available."""
        logger.info("Scraping player directory...")
        
        # Try to find player search/directory
        urls_to_try = [
            "https://www.digitalpool.com/players",
            "https://www.digitalpool.com/search?type=player",
        ]
        
        for url in urls_to_try:
            response = self.fetch_page(url)
            if response and response.status_code == 200:
                logger.info(f"  Found player directory at {url}")
                self._parse_player_directory(response)
                break
        
        logger.info(f"Total players found: {len(self.players)}")
    
    def _parse_player_directory(self, response):
        """Parse player directory content."""
        soup = BeautifulSoup(response.content, 'html.parser')
        
        player_links = soup.find_all('a', href=re.compile(r'/player/'))
        
        for link in player_links:
            try:
                name = link.get_text(strip=True)
                url = link.get('href', '')
                
                if name and url:
                    self.players[name] = {
                        'name': name,
                        'url': url,
                        'country': None,
                    }
            except Exception as e:
                logger.debug(f"Error parsing player link: {e}")
    
    def scrape_venues(self):
        """Scrape venue information."""
        logger.info("Scraping venue information...")
        
        response = self.fetch_page("https://www.digitalpool.com/venues")
        if not response:
            return
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        venue_elements = soup.find_all(re.compile(r'venue'))
        
        for elem in venue_elements:
            try:
                venue_name = elem.get_text(strip=True)
                if venue_name:
                    self.venues[venue_name] = {'name': venue_name}
            except Exception as e:
                logger.debug(f"Error parsing venue: {e}")
        
        logger.info(f"Total venues found: {len(self.venues)}")
    
    def save_archive(self):
        """Save all scraped data to JSON archive."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        archive_file = self.output_dir / f"cp_archive_{timestamp}.json"
        
        data = {
            'scraped_at': datetime.now().isoformat(),
            'tournaments': self.tournaments,
            'players': self.players,
            'venues': self.venues,
            'country_mapping': self.country_mapping,
            'summary': {
                'tournaments_count': len(self.tournaments),
                'players_count': len(self.players),
                'venues_count': len(self.venues),
            }
        }
        
        with open(archive_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Archive saved to {archive_file}")
        logger.info(f"  - Tournaments: {len(self.tournaments)}")
        logger.info(f"  - Players: {len(self.players)}")
        logger.info(f"  - Venues: {len(self.venues)}")
        
        return archive_file
    
    def run(self, include_brackets=False):
        """Run comprehensive scrape."""
        logger.info("=" * 70)
        logger.info("Starting CP Comprehensive Scrape")
        logger.info("=" * 70)
        
        # Scrape tournament listings
        self.scrape_tournaments_list()
        
        # Optionally scrape detailed tournament data
        if include_brackets and self.tournaments:
            logger.info(f"Scraping details for {min(5, len(self.tournaments))} tournaments...")
            for tournament in self.tournaments[:5]:  # Limit to first 5 for initial run
                details = self.scrape_tournament_details(tournament['url'])
                if details:
                    tournament.update(details)
                time.sleep(1)  # Rate limiting
        
        # Scrape players directory
        self.scrape_players_directory()
        
        # Scrape venues
        self.scrape_venues()
        
        # Save archive
        archive_file = self.save_archive()
        
        logger.info("=" * 70)
        logger.info("Scrape Complete")
        logger.info("=" * 70)
        
        return archive_file

if __name__ == '__main__':
    scraper = CpScraper()
    scraper.run(include_brackets=False)
