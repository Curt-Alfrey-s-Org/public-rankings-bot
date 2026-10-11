#!/usr/bin/env python3
"""
Selenium-based ExternalPool scraper for JavaScript-rendered content

Falls back to requests if Selenium not available.
"""

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

class BrowserBasedScraper:
    """Scraper using browser automation for JavaScript-rendered content."""
    
    def __init__(self, output_dir='data/externalpool_archive'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.use_selenium = self._check_selenium()
        self.use_playwright = self._check_playwright()
        
        if not (self.use_selenium or self.use_playwright):
            logger.warning("Neither Selenium nor Playwright available. Install with:")
            logger.warning("  pip install selenium playwright")
            logger.warning("  python -m playwright install")
    
    def _check_selenium(self):
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            self.webdriver = webdriver
            self.Options = Options
            logger.info("✓ Selenium available")
            return True
        except ImportError:
            return False
    
    def _check_playwright(self):
        try:
            import playwright
            self.playwright = playwright
            logger.info("✓ Playwright available")
            return True
        except ImportError:
            return False
    
    def scrape_with_selenium(self, url):
        """Scrape using Selenium."""
        try:
            options = self.Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            driver = self.webdriver.Chrome(options=options)
            logger.info(f"  Fetching {url} with Selenium...")
            
            driver.get(url)
            time.sleep(3)  # Wait for JavaScript to render
            
            html = driver.page_source
            driver.quit()
            
            return html
        except Exception as e:
            logger.error(f"Selenium error: {e}")
            return None
    
    async def scrape_with_playwright(self, url):
        """Scrape using Playwright."""
        try:
            async with self.playwright.async_api() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                logger.info(f"  Fetching {url} with Playwright...")
                
                await page.goto(url, wait_until='networkidle')
                time.sleep(2)  # Extra wait for dynamic content
                
                html = await page.content()
                await browser.close()
                
                return html
        except Exception as e:
            logger.error(f"Playwright error: {e}")
            return None
    
    def _extract_tournament_data(self, html, tournament_name, tournament_url):
        """Extract structured data from tournament HTML."""
        data = {
            'tournament_name': tournament_name,
            'url': tournament_url,
            'players': [],
            'matches': [],
            'standings': [],
        }
        
        # Extract player names and countries
        # Look for player entries with various patterns
        
        # Pattern 1: Player with flag image
        # <img src="/flags/us.svg"> PlayerName
        player_patterns = [
            r'<img[^>]*src=["\'].*?/flags/([a-z]{2})\.svg["\'][^>]*>\s*([A-Z][a-zA-Z\s\-\.\']+)',
            r'<td[^>]*data-country=["\']([a-z]{2})["\'][^>]*>([A-Z][a-zA-Z\s\-\.\']+)',
            r'<span[^>]*class=["\'][^"\']*flag[^"\']*["\'][^>]*data-code=["\']([a-z]{2})["\'][^>]*>.*?<span>([A-Z][a-zA-Z\s\-\.\']+)',
        ]
        
        for pattern in player_patterns:
            for match in re.finditer(pattern, html, re.IGNORECASE):
                try:
                    if len(match.groups()) >= 2:
                        country_code = match.group(1).lower()
                        player_name = match.group(2).strip()
                        
                        if player_name and len(player_name) > 2:
                            data['players'].append({
                                'name': player_name,
                                'country_code': country_code,
                            })
                except Exception as e:
                    logger.debug("Could not parse player regex match '%s': %s", match.group(0), e)
        
        # Extract match results
        # Pattern: PlayerA vs PlayerB (score1-score2)
        match_patterns = [
            r'([A-Z][a-zA-Z\s\-\.\']+)\s+(?:vs|-)\s+([A-Z][a-zA-Z\s\-\.\']+)\s+\((\d+)-(\d+)\)',
            r'<tr[^>]*class=["\'][^"\']*match[^"\']*["\'][^>]*>.*?<td>([A-Z][a-zA-Z\s\-\.\']+)</td>.*?<td>(\d+)-(\d+)</td>.*?<td>([A-Z][a-zA-Z\s\-\.\']+)</td>',
        ]
        
        for pattern in match_patterns:
            for match in re.finditer(pattern, html, re.IGNORECASE | re.DOTALL):
                try:
                    if len(match.groups()) >= 4:
                        operator = match.group(1).strip() if len(match.groups()) >= 1 else ''
                        player2 = match.group(2 if len(match.groups()) >= 4 else 4).strip() if len(match.groups()) >= 2 else ''
                        score1 = int(match.group(3 if len(match.groups()) >= 4 else 2))
                        score2 = int(match.group(4 if len(match.groups()) >= 4 else 3))
                        
                        if 0 <= score1 <= 11 and 0 <= score2 <= 11:
                            data['matches'].append({
                                'operator': operator,
                                'player2': player2,
                                'score1': score1,
                                'score2': score2,
                            })
                except Exception as e:
                    logger.debug("Could not parse match regex '%s': %s", match.group(0), e)
        
        # Remove duplicates
        seen_players = set()
        unique_players = []
        for p in data['players']:
            key = (p['name'], p['country_code'])
            if key not in seen_players:
                seen_players.add(key)
                unique_players.append(p)
        data['players'] = unique_players
        
        return data
    
    def run(self):
        """Run browser-based scraper."""
        logger.info("=" * 70)
        logger.info("Browser-Based ExternalPool Scraper")
        logger.info("=" * 70)
        
        if not (self.use_selenium or self.use_playwright):
            logger.error("No browser automation library available. Exiting.")
            return
        
        tournaments = [
            {
                'name': '2026 WPBA Classic Players Championship',
                'url': 'https://www.digitalpool.com/tournaments/2026-wpba-classics-players-championship/bracket',
            },
            {
                'name': '2025 WPBA Olhausen Colorado Classic',
                'url': 'https://www.digitalpool.com/tournaments/2025-wpba-olhausen-colorado-classic/bracket',
            },
            {
                'name': '2025 WPBA Iron City Invitational VI',
                'url': 'https://www.digitalpool.com/tournaments/2025-olhausen-iron-city-invitational-vi/bracket',
            },
        ]
        
        all_data = []
        
        for tournament in tournaments:
            try:
                name = tournament['name']
                url = tournament['url']
                
                logger.info(f"\nScraping: {name}")
                
                # Get HTML
                if self.use_selenium:
                    html = self.scrape_with_selenium(url)
                else:
                    # Would need async context for Playwright
                    logger.info("  (Playwright requires async context, skipping)")
                    html = None
                
                if html:
                    # Extract data
                    data = self._extract_tournament_data(html, name, url)
                    all_data.append(data)
                    
                    logger.info(f"  Players: {len(data['players'])}")
                    logger.info(f"  Matches: {len(data['matches'])}")
                
                time.sleep(2)  # Rate limit
            
            except Exception as e:
                logger.error(f"Error scraping {name}: {e}")
        
        # Save results
        self._save_results(all_data)
        
        logger.info("=" * 70)
        logger.info("Scraping Complete")
        logger.info("=" * 70)
    
    def _save_results(self, data):
        """Save results to JSON."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        archive = {
            'scraped_at': datetime.now().isoformat(),
            'method': 'selenium' if self.use_selenium else 'playwright',
            'tournaments': data,
            'summary': {
                'total_tournaments': len(data),
                'total_players': sum(len(t['players']) for t in data),
                'total_matches': sum(len(t['matches']) for t in data),
            }
        }
        
        filename = self.output_dir / f"browser_scraped_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(archive, f, indent=2)
        
        logger.info(f"\nResults saved to: {filename}")
        logger.info(f"  Total players: {archive['summary']['total_players']}")
        logger.info(f"  Total matches: {archive['summary']['total_matches']}")

if __name__ == '__main__':
    scraper = BrowserBasedScraper()
    scraper.run()
