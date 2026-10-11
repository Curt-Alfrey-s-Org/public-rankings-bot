#!/usr/bin/env python3
"""
ExternalPool API-based scraper

Since ExternalPool is a React SPA, we need to reverse-engineer the API endpoints.
This scraper inspects network traffic patterns and makes direct API calls.
"""

import requests
import json
import logging
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class CpAPIScraper:
    def __init__(self, output_dir='data/cp_archive'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.digitalpool.com/',
            'Origin': 'https://www.digitalpool.com',
        })
        
        self.base_url = 'https://www.digitalpool.com'
        self.api_patterns = [
            '/api/v1/tournaments',
            '/api/tournaments',
            '/api/v1/bracket',
            '/api/bracket',
            '/api/v1/players',
            '/api/players',
        ]
    
    def find_tournament_api(self, tournament_slug):
        """Find API endpoint for a tournament."""
        logger.info(f"Finding API for tournament: {tournament_slug}")
        
        # Try common API patterns
        api_attempts = [
            f"{self.base_url}/api/v1/tournaments/{tournament_slug}",
            f"{self.base_url}/api/tournaments/{tournament_slug}",
            f"{self.base_url}/api/v1/tournaments/{tournament_slug}/bracket",
            f"{self.base_url}/api/tournaments/{tournament_slug}/bracket",
            f"{self.base_url}/api/v1/brackets/{tournament_slug}",
            f"{self.base_url}/api/tournaments/{tournament_slug}/players",
        ]
        
        for url in api_attempts:
            try:
                response = self.session.get(url, timeout=5)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data and (isinstance(data, dict) and len(data) > 0 or isinstance(data, list) and len(data) > 0):
                            logger.info(f"  ✓ Found working API: {url}")
                            return url, data
                    except Exception as e:
                        logger.debug("Could not parse API response JSON from %s: %s", url, e)
            except Exception as e:
                logger.debug("API probe failed for %s: %s", url, e)
        
        logger.warning(f"  No working API found for {tournament_slug}")
        return None, None
    
    def scrape_tournament_data(self, tournament_info):
        """Scrape complete tournament data."""
        slug = tournament_info['slug']
        name = tournament_info['name']
        
        logger.info(f"\nScraping: {name}")
        
        # Find bracket API
        api_url, data = self.find_tournament_api(slug)
        
        if not api_url or not data:
            # Fallback: try to get it from tournament page
            logger.info(f"  Trying alternative approach...")
            return None
        
        # Extract structured data
        tournament_data = self._process_api_response(data, name)
        
        logger.info(f"  Players: {len(tournament_data.get('players', []))}")
        logger.info(f"  Matches: {len(tournament_data.get('matches', []))}")
        
        return tournament_data
    
    def _process_api_response(self, data, tournament_name):
        """Process API response and extract structure."""
        result = {
            'tournament_name': tournament_name,
            'players': [],
            'matches': [],
            'standings': [],
        }
        
        # Handle different response structures
        if isinstance(data, dict):
            # Extract from various possible keys
            for key in ['bracket', 'brackets', 'players', 'participants', 'entries']:
                if key in data:
                    items = data[key]
                    if isinstance(items, list):
                        result['players'].extend(self._extract_players(items))
            
            # Look for match results
            for key in ['matches', 'rounds', 'results']:
                if key in data:
                    items = data[key]
                    if isinstance(items, list):
                        result['matches'].extend(self._extract_matches(items))
            
            # Look for standings/results
            for key in ['standings', 'results', 'final_results']:
                if key in data:
                    items = data[key]
                    if isinstance(items, list):
                        result['standings'].extend(items[:100])
        
        elif isinstance(data, list):
            # Try to interpret array data
            result['players'] = self._extract_players(data)
        
        return result
    
    def _extract_players(self, items):
        """Extract player data from various structures."""
        players = []
        
        for item in items:
            if isinstance(item, dict):
                # Try various field names
                player = {}
                
                for name_key in ['name', 'player_name', 'player', 'username', 'user_name']:
                    if name_key in item:
                        player['name'] = item[name_key]
                        break
                
                for country_key in ['country', 'country_code', 'country_id', 'flag']:
                    if country_key in item:
                        player['country_code'] = str(item[country_key])[:2].lower()
                        break
                
                if 'name' in player:
                    players.append(player)
            
            elif isinstance(item, str):
                # Simple string list of names
                players.append({'name': item, 'country_code': ''})
        
        return players
    
    def _extract_matches(self, items):
        """Extract match data from various structures."""
        matches = []
        
        for item in items:
            if isinstance(item, dict):
                match = {}
                
                # Try various field patterns
                if 'p1_score' in item and 'p2_score' in item:
                    match = {
                        'operator': item.get('operator', item.get('p1', '')),
                        'player2': item.get('player2', item.get('p2', '')),
                        'score1': int(item['p1_score']),
                        'score2': int(item['p2_score']),
                    }
                
                elif 'score' in item:
                    scores = item['score']
                    if isinstance(scores, list) and len(scores) >= 2:
                        match = {
                            'operator': item.get('operator', item.get('p1', '')),
                            'player2': item.get('player2', item.get('p2', '')),
                            'score1': int(scores[0]),
                            'score2': int(scores[1]),
                        }
                
                if 'score1' in match and 0 <= match['score1'] <= 11 and 0 <= match['score2'] <= 11:
                    matches.append(match)
        
        return matches
    
    def run(self):
        """Run API-based scraper."""
        logger.info("=" * 70)
        logger.info("CP API-Based Scraper")
        logger.info("=" * 70)
        
        tournaments = [
            {
                'slug': '2026-wpba-classics-players-championship',
                'name': '2026 WPBA Classic Players Championship',
            },
            {
                'slug': '2025-wpba-olhausen-colorado-classic',
                'name': '2025 WPBA Olhausen Colorado Classic',
            },
            {
                'slug': '2025-olhausen-iron-city-invitational-vi',
                'name': '2025 WPBA Iron City Invitational VI',
            },
        ]
        
        results = []
        
        # Try API approach
        for tournament in tournaments:
            data = self.scrape_tournament_data(tournament)
            if data:
                results.append(data)
            
            time.sleep(1)
        
        # Save results
        if results:
            self._save_results(results, 'api_based')
        else:
            logger.warning("No data collected via API. Recommending browser-based approach.")
            self._save_results([], 'api_based_empty')
    
    def _save_results(self, data, method):
        """Save results to JSON."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        archive = {
            'scraped_at': datetime.now().isoformat(),
            'method': method,
            'tournament_count': len(data),
            'tournaments': data,
        }
        
        filename = self.output_dir / f"api_scrape_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(archive, f, indent=2)
        
        logger.info(f"\nResults saved to: {filename}")
        if data:
            logger.info(f"  Tournaments: {len(data)}")
            logger.info(f"  Total players: {sum(len(t.get('players', [])) for t in data)}")

if __name__ == '__main__':
    scraper = CpAPIScraper()
    scraper.run()
