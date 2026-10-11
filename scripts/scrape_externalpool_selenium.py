#!/usr/bin/env python3
"""
Production-ready Selenium-based ExternalPool scraper

Properly handles JavaScript rendering and extracts tournament bracket data.
"""

import json
import logging
import time
from pathlib import Path
from datetime import datetime, date
import argparse
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import re
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class CpSeleniumScraper:
    """Production Selenium scraper for CP (external pool)."""

    def __init__(self, output_dir='data/cp_archive', headless=True):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.headless = headless
        self.driver = None
        self.wait = None
    
    def _init_driver(self):
        """Initialize Chrome WebDriver."""
        options = Options()
        
        if self.headless:
            options.add_argument('--headless')
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36')
        
        # Disable images and CSS for faster loading
        options.add_argument('--blink-settings=imagesEnabled=false')
        
        try:
            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 15)
            logger.info("✓ WebDriver initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            logger.info("Install chromedriver with: brew install chromedriver (macOS) or apt install chromium-chromedriver (Linux)")
            return False
    
    def _quit_driver(self):
        """Close WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.wait = None

    def _normalize_tournament_url(self, href: str) -> str:
        """Normalize tournament URL and force bracket route for consistency."""
        if not href:
            return ""
        href = href.strip()
        if href.startswith("/"):
            href = f"https://www.digitalpool.com{href}"
        if not href.startswith("http"):
            return ""
        # Strip query/hash and ensure bracket endpoint
        parsed = urlparse(href)
        path = parsed.path.rstrip("/")
        if not path.endswith("/bracket"):
            path = f"{path}/bracket"
        return f"https://{parsed.netloc}{path}"

    def _slug_to_title(self, slug: str) -> str:
        words = [w for w in slug.replace("-", " ").split() if w]
        return " ".join(w.upper() if w.lower() in {"wpa", "wpba"} else w.capitalize() for w in words)

    def _infer_association(self, name: str) -> str:
        up = (name or "").upper()
        if "WPBA" in up:
            return "WPBA"
        if "HEYBALL" in up:
            return "WPA Heyball"
        if "ARTISTIC" in up:
            return "WPA Artistic"
        if "WPA" in up and ("WOMEN" in up or "LADIES" in up):
            return "WPA Women"
        if "WPA" in up:
            return "WPA Men"
        return "WPA"

    def _extract_ldjson_event_date(self, html: str) -> str | None:
        """Extract endDate (or startDate) from Event JSON-LD in page HTML."""
        scripts = re.findall(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        for s in scripts:
            try:
                blob = json.loads(s.strip())
            except Exception:
                continue
            nodes = blob if isinstance(blob, list) else [blob]
            for n in nodes:
                if not isinstance(n, dict):
                    continue
                if "event" not in str(n.get("@type", "")).lower():
                    continue
                end_date = str(n.get("endDate") or n.get("startDate") or "")[:10]
                if re.match(r"^\d{4}-\d{2}-\d{2}$", end_date):
                    return end_date
        return None

    def _discover_tournaments(self, max_tournaments: int = 20):
        """Discover tournament links dynamically from External Pool listing page."""
        base_url = "https://www.digitalpool.com/tournaments"
        logger.info("Discovering tournaments from %s", base_url)
        self.driver.get(base_url)
        time.sleep(2)

        # Scroll to trigger lazy content loading.
        for _ in range(4):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.2)

        anchors = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/tournaments/')]")
        discovered = []
        seen = set()
        current_year = date.today().year
        for a in anchors:
            href = a.get_attribute("href") or ""
            text = (a.text or "").strip()
            url = self._normalize_tournament_url(href)
            if not url or url in seen:
                continue
            seen.add(url)
            slug = urlparse(url).path.strip("/").split("/")[-2] if "/tournaments/" in url else ""
            name = text if len(text) > 5 else self._slug_to_title(slug)

            # Keep likely tournament pages, prioritizing current/future years in slug or title.
            if "/tournaments/" not in url:
                continue
            has_future_hint = any(str(y) in f"{name} {slug}" for y in (current_year, current_year + 1, current_year + 2))
            if not has_future_hint and len(discovered) >= max_tournaments:
                continue

            discovered.append({"url": url, "name": name})
            if len(discovered) >= max_tournaments:
                break

        if discovered:
            logger.info("Discovered %s tournament URLs", len(discovered))
            return discovered

        logger.warning("No links discovered from listing page; using fallback candidates.")
        fallback = self._fallback_tournaments(max_tournaments=max_tournaments)
        logger.info("Fallback discovered %s tournament URLs", len(fallback))
        return fallback

    def _slugify(self, text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
        slug = slug.replace("-s-", "s-")
        return re.sub(r"-+", "-", slug)

    def _url_is_reachable(self, url: str) -> bool:
        try:
            r = requests.get(url, timeout=8, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            return r.status_code < 400 and "tournament not found" not in (r.text or "").lower()
        except Exception:
            return False

    def _fallback_tournaments(self, max_tournaments: int = 20):
        """
        Fallback URL discovery when /tournaments page hides links behind JS.
        Uses known working slugs + generated slugs from local archives.
        """
        candidates = []
        seen = set()

        def add(name: str, url: str):
            if not url:
                return
            norm = self._normalize_tournament_url(url)
            if not norm or norm in seen:
                return
            seen.add(norm)
            candidates.append({"name": name or self._slug_to_title(urlparse(norm).path), "url": norm})

        # Known working URLs
        add("2026 WPBA Classic Players Championship", "https://www.digitalpool.com/tournaments/2026-wpba-classics-players-championship/bracket")
        add("2025 WPBA Olhausen Colorado Classic", "https://www.digitalpool.com/tournaments/2025-wpba-olhausen-colorado-classic/bracket")
        add("2025 WPBA Iron City Invitational VI", "https://www.digitalpool.com/tournaments/2025-olhausen-iron-city-invitational-vi/bracket")

        # Most recent CP archives
        for p in sorted(self.output_dir.glob("selenium_scraped_*.json"), reverse=True)[:8]:
            try:
                payload = json.loads(p.read_text())
                for t in payload.get("tournaments", []):
                    add(t.get("tournament_name") or t.get("name") or "", t.get("url") or "")
            except Exception:
                continue

        # Generate candidate slugs from local current tournaments archive names
        current_archive_dir = Path("data/tournament_current_archive")
        for p in sorted(current_archive_dir.glob("tournament_current_tournaments_*.json"), reverse=True)[:2]:
            try:
                payload = json.loads(p.read_text())
                for row in payload.get("data", []):
                    name = (row.get("name") or "").strip()
                    if not name or "WPBA" not in name.upper():
                        continue
                    slug = self._slugify(name)
                    add(name, f"https://www.digitalpool.com/tournaments/{slug}/bracket")
            except Exception:
                continue

        # Keep only reachable pages and cap to max_tournaments
        reachable = []
        for c in candidates:
            if self._url_is_reachable(c["url"]):
                reachable.append(c)
            if len(reachable) >= max_tournaments:
                break
        return reachable
    
    def scrape_tournament(self, url, tournament_name, metadata_only=True):
        """Scrape a single tournament."""
        logger.info(f"\nScraping: {tournament_name}")
        logger.info(f"  URL: {url}")
        
        try:
            self.driver.get(url)
            logger.info("  ✓ Page loaded")
            
            # Wait for page content to render (up to 15 seconds)
            time.sleep(3)
            
            # Try to find tournament data in multiple ways
            tournament_data = {
                'tournament_name': tournament_name,
                'url': url,
                'association': self._infer_association(tournament_name),
                'date': None,
                'status': 'unknown',
                'players': [],
                'matches': [],
                'standings': [],
                'scraped_at': datetime.now().isoformat(),
            }

            html = self.driver.page_source
            event_date = self._extract_ldjson_event_date(html)
            tournament_data['date'] = event_date
            if event_date:
                try:
                    d = datetime.strptime(event_date, "%Y-%m-%d").date()
                    tournament_data['status'] = 'upcoming' if d >= date.today() else 'completed'
                except Exception:
                    tournament_data['status'] = 'unknown'
            else:
                # Keep as upcoming when date is missing; upstream filters later.
                tournament_data['status'] = 'upcoming'
            
            if not metadata_only:
                # Method 1: Look for player elements by text content
                logger.info("  Extracting players...")
                tournament_data['players'] = self._extract_players()
                
                # Method 2: Look for match results
                logger.info("  Extracting matches...")
                tournament_data['matches'] = self._extract_matches()
                
                # Method 3: Look for standings/results
                logger.info("  Extracting standings...")
                tournament_data['standings'] = self._extract_standings()
            
            logger.info(f"  ✓ Players: {len(tournament_data['players'])}, Matches: {len(tournament_data['matches'])}")
            
            return tournament_data
        
        except Exception as e:
            logger.error(f"  Error scraping tournament: {e}")
            return None
    
    def _extract_players(self):
        """Extract player list from rendered page."""
        players = []
        
        try:
            # Get page source to search for player names
            html = self.driver.page_source
            
            # Pattern: Look for player names in various contexts
            # Player names are typically 3-50 characters, capitalized
            
            # Look in specific divs/sections
            player_elements = self.driver.find_elements(By.XPATH, 
                "//*[contains(@class, 'player') and text()]" +
                " | //*[contains(@data-player, '')] " +
                " | //span[contains(@class, 'name')] " +
                " | //div[contains(text(), ' vs ')]"
            )
            
            seen = set()
            for elem in player_elements[:200]:  # Limit to first 200
                try:
                    text = elem.text.strip()
                    if 3 < len(text) < 50 and text not in seen:
                        # Skip common non-player text
                        if not any(skip in text.lower() for skip in ['bracket', 'match', 'score', 'seed', '–', '—']):
                            seen.add(text)
                            players.append({
                                'name': text,
                                'country_code': '',
                            })
                except Exception as e:
                    logger.debug("Could not parse player element text: %s", e)
            
            # Also search HTML for patterns like "PlayerName vs PlayerName"
            vs_matches = re.findall(
                r'([A-Z][a-zA-Z\s\-\.\']{2,49}) vs? ([A-Z][a-zA-Z\s\-\.\']{2,49})',
                html
            )
            
            for match in vs_matches:
                for name in match:
                    if name not in seen:
                        seen.add(name)
                        players.append({
                            'name': name,
                            'country_code': '',
                        })
            
            return players[:500]  # Limit to 500 unique players
        
        except Exception as e:
            logger.warning(f"  Error extracting players: {e}")
            return []
    
    def _extract_matches(self):
        """Extract match results from rendered page."""
        matches = []
        
        try:
            html = self.driver.page_source
            
            # Pattern: "Operator vs Player2 (9-6)" or similar score formats
            match_pattern = r'([A-Z][a-zA-Z\s\-\.\']{2,49})\s+vs?\s+([A-Z][a-zA-Z\s\-\.\']{2,49})\s*[\(\s]*(\d+)[:\-\s]+(\d+)'
            
            for match in re.finditer(match_pattern, html):
                try:
                    score1 = int(match.group(3))
                    score2 = int(match.group(4))
                    
                    if 0 <= score1 <= 11 and 0 <= score2 <= 11:
                        matches.append({
                            'operator': match.group(1).strip(),
                            'player2': match.group(2).strip(),
                            'score1': score1,
                            'score2': score2,
                        })
                except Exception as e:
                    logger.debug("Could not parse match pattern '%s': %s", match.group(0), e)
            
            # Remove duplicates
            seen = set()
            unique_matches = []
            for m in matches:
                key = (m['operator'], m['player2'], m['score1'], m['score2'])
                if key not in seen:
                    seen.add(key)
                    unique_matches.append(m)
            
            return unique_matches[:1000]  # Limit to 1000 matches
        
        except Exception as e:
            logger.warning(f"  Error extracting matches: {e}")
            return []
    
    def _extract_standings(self):
        """Extract tournament standings/results."""
        standings = []
        
        try:
            # Look for table rows with ranking info
            rows = self.driver.find_elements(By.XPATH, "//tr")
            
            for row in rows[:100]:  # First 100 rows
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 2:
                        text_content = ' '.join([cell.text for cell in cells]).strip()
                        if len(text_content) > 5:
                            standings.append({
                                'position': len(standings) + 1,
                                'data': text_content,
                            })
                except Exception as e:
                    logger.debug("Could not parse standings row: %s", e)
            
            return standings[:200]
        
        except Exception as e:
            logger.warning(f"  Error extracting standings: {e}")
            return []
    
    def run(self, max_tournaments: int = 20, metadata_only: bool = True):
        """Run Selenium scraper."""
        logger.info("=" * 70)
        logger.info("CP Selenium Scraper (Production Version)")
        logger.info("=" * 70)
        
        # Initialize driver
        if not self._init_driver():
            return
        
        try:
            tournaments = self._discover_tournaments(max_tournaments=max_tournaments)
            if not tournaments:
                logger.warning("No tournament links discovered from listing page.")
                return
            
            results = []
            
            for tournament in tournaments:
                data = self.scrape_tournament(
                    tournament['url'],
                    tournament['name'],
                    metadata_only=metadata_only,
                )
                if data:
                    results.append(data)
                
                # Rate limiting
                time.sleep(1.5)
            
            # Save results
            self._save_results(results)
        
        finally:
            self._quit_driver()
    
    def _save_results(self, data):
        """Save scraped data to JSON."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        archive = {
            'scraped_at': datetime.now().isoformat(),
            'method': 'selenium_chrome',
            'tournament_count': len(data),
            'total_players': sum(len(t.get('players', [])) for t in data),
            'total_matches': sum(len(t.get('matches', [])) for t in data),
            'tournaments': data,
        }
        
        filename = self.output_dir / f"selenium_scraped_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(archive, f, indent=2)
        
        logger.info("\n" + "=" * 70)
        logger.info(f"Results saved to: {filename}")
        logger.info(f"  Tournaments: {archive['tournament_count']}")
        logger.info(f"  Total players: {archive['total_players']}")
        logger.info(f"  Total matches: {archive['total_matches']}")
        logger.info("=" * 70)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Selenium External Pool scraper")
    parser.add_argument("--max", type=int, default=20, help="Max tournaments to scrape")
    parser.add_argument("--full", action="store_true", help="Also extract players/matches/standings")
    parser.add_argument("--headed", action="store_true", help="Run browser in non-headless mode")
    args = parser.parse_args()

    scraper = CpSeleniumScraper(headless=not args.headed)
    scraper.run(max_tournaments=args.max, metadata_only=not args.full)
