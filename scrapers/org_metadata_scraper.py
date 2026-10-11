#!/usr/bin/env python3
"""
Organization Metadata Scraper
Fetches organization information: logo, theme colors, layout styles, etc.
"""

import logging
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional

from scrapers.fetch_utils import get_with_retry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrgMetadataScraper:
    """Scraper for organization metadata (logos, themes, colors, etc.)"""
    
    def __init__(self, timeout: int = 30):
        """
        Initialize org metadata scraper
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # Save location for scraped data
        self.scraped_data_dir = Path("scraped_data/org_metadata")
        self.scraped_data_dir.mkdir(parents=True, exist_ok=True)

        # Organization URLs and metadata
        self.orgs = {
            'wpba': {
                'name': 'Women\'s Professional Billiards Association',
                'url': 'https://wpba.com',  # Official domain (wpbapool.com does not resolve)
                'logo': None,
                'primary_color': '#FF1493',  # Default
                'secondary_color': '#FFFFFF',
                'theme': 'pink'
            },
            'wpa': {
                'name': 'World Pool Association',
                'url': 'https://wpapool.com',
                'logo': None,
                'primary_color': '#003366',  # Default
                'secondary_color': '#FFFFFF',
                'theme': 'blue'
            }
        }
    
    def scrape_wpba_metadata(self) -> Dict:
        """
        Scrape WPBA organization metadata

        Returns:
            Dict with org metadata: logo, colors, theme, layout
        """
        logger.info("Fetching WPBA metadata from %s", self.orgs['wpba']['url'])
        
        try:
            response = get_with_retry(
                self.orgs['wpba']['url'],
                timeout=self.timeout,
                max_retries=2,
                session=self.session,
            )
            soup = BeautifulSoup(response.text, 'html.parser')
            
            metadata = {
                'org': 'WPBA',
                'name': 'Women\'s Professional Billiards Association',
                'url': self.orgs['wpba']['url'],
                'logo': self._extract_logo(soup, 'wpba'),
                'primary_color': self._extract_color(soup, 'wpba'),
                'theme': 'women-friendly',
                'layout': 'modern',
                'description': 'Professional womens pool rankings'
            }
            
            logger.info("Successfully scraped WPBA metadata")
            return metadata
            
        except Exception as e:
            logger.error("WPBA metadata scrape failed: %s", e)
            raise
    
    def scrape_wpa_metadata(self) -> Dict:
        """
        Scrape WPA organization metadata

        Returns:
            Dict with org metadata: logo, colors, theme, layout
        """
        logger.info("Fetching WPA metadata from %s", self.orgs['wpa']['url'])
        
        try:
            response = get_with_retry(
                self.orgs['wpa']['url'],
                timeout=self.timeout,
                max_retries=2,
                session=self.session,
            )
            soup = BeautifulSoup(response.text, 'html.parser')
            
            metadata = {
                'org': 'WPA',
                'name': 'World Pool Association',
                'url': self.orgs['wpa']['url'],
                'logo': self._extract_logo(soup, 'wpa'),
                'primary_color': self._extract_color(soup, 'wpa'),
                'theme': 'professional',
                'layout': 'classic',
                'description': 'World professional pool rankings'
            }
            
            logger.info("Successfully scraped WPA metadata")
            return metadata
            
        except Exception as e:
            logger.error("WPA metadata scrape failed: %s", e)
            raise
    
    def _extract_logo(self, soup: BeautifulSoup, org: str) -> Optional[str]:
        """
        Extract logo URL from page
        
        Args:
            soup: BeautifulSoup object
            org: 'wpba' or 'wpa'
            
        Returns:
            Logo URL or None
        """
        try:
            # Look for logo image
            img_selectors = [
                'img[alt*="logo"]',
                'img[class*="logo"]',
                'img[class*="brand"]',
                '.navbar img',
                '.header img'
            ]
            
            for selector in img_selectors:
                imgs = soup.select(selector)
                if imgs:
                    src = imgs[0].get('src')
                    if src:
                        return src if src.startswith('http') else f"https://{org}pool.com{src}"
            
            return None
            
        except Exception as e:
            logger.warning("Could not extract logo: %s", e)
            return None
    
    def _extract_color(self, soup: BeautifulSoup, org: str) -> str:
        """
        Extract primary brand color from page CSS/styles
        
        Args:
            soup: BeautifulSoup object
            org: 'wpba' or 'wpa'
            
        Returns:
            Hex color code
        """
        try:
            # Look in style tags for primary colors
            styles = soup.find_all('style')
            colors = ['#FF1493', '#003366', '#1E90FF', '#FFB6C1', '#4169E1']
            
            color_pattern = re.compile(r'#[0-9A-Fa-f]{6}')
            
            for style in styles:
                found_colors = color_pattern.findall(style.string or '')
                if found_colors:
                    # Return most common color
                    return found_colors[0]
            
            # Fall back to defaults
            return self.orgs[org]['primary_color']
            
        except Exception as e:
            logger.warning("Could not extract color: %s", e)
            return self.orgs[org]['primary_color']
    
    def get_all_metadata(self) -> Dict[str, Dict]:
        """
        Get metadata for all organizations
        
        Returns:
            Dict mapping org codes to metadata dicts
        """
        return {
            'wpba': self.scrape_wpba_metadata(),
            'wpa': self.scrape_wpa_metadata(),
        }


if __name__ == '__main__':
    scraper = OrgMetadataScraper()
    metadata = scraper.get_all_metadata()
    
    for org_code, data in metadata.items():
        print(f"\n{org_code.upper()}:")
        for key, val in data.items():
            print(f"  {key}: {val}")
