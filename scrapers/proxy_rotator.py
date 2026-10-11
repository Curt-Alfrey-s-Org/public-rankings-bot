"""
Proxy rotation utilities for respectful web scraping.
Supports both free proxy lists and paid proxy services.
"""

import logging
import os
import json
from typing import Optional, List, Dict
from pathlib import Path
import requests

logger = logging.getLogger(__name__)


class ProxyRotator:
    """Manages rotating proxy list for scraping."""
    
    def __init__(self, proxy_list: List[str] = None, proxy_file: str = None):
        """
        Initialize proxy rotator.
        
        Args:
            proxy_list: List of proxy URLs (http://ip:port or socks5://ip:port)
            proxy_file: Path to JSON file with proxy list
        """
        self.proxies = []
        self.current_index = 0
        
        if proxy_list:
            self.proxies = proxy_list
            logger.info(f"Initialized with {len(proxy_list)} proxies from argument")
        elif proxy_file and Path(proxy_file).exists():
            with open(proxy_file) as f:
                data = json.load(f)
                self.proxies = data.get('proxies', []) if isinstance(data, dict) else data
            logger.info(f"Loaded {len(self.proxies)} proxies from {proxy_file}")
        elif os.getenv('SCRAPER_PROXIES'):
            # CSV list from environment
            self.proxies = [p.strip() for p in os.getenv('SCRAPER_PROXIES').split(',')]
            logger.info(f"Loaded {len(self.proxies)} proxies from SCRAPER_PROXIES env var")
        
        if not self.proxies:
            logger.warning("No proxies configured - will scrape without proxy")
    
    def get_next_proxy(self) -> Optional[Dict[str, str]]:
        """
        Get next proxy in rotation.
        
        Returns:
            Dict with 'http' and 'https' keys, or None if no proxies
        """
        if not self.proxies:
            return None
        
        proxy_url = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        
        # Format for requests library
        return {
            'http': proxy_url,
            'https': proxy_url,
        }
    
    def get_proxy_dict(self) -> Optional[Dict[str, str]]:
        """Alias for get_next_proxy for backwards compatibility."""
        return self.get_next_proxy()
    
    def reset(self):
        """Reset to first proxy."""
        self.current_index = 0
    
    def add_proxy(self, proxy: str):
        """Add a proxy to the list."""
        if proxy not in self.proxies:
            self.proxies.append(proxy)
    
    def remove_proxy(self, proxy: str):
        """Remove a proxy from the list."""
        if proxy in self.proxies:
            self.proxies.remove(proxy)


class SimpleProxyLoader:
    """Load proxies from free-proxy-list.net (NOTE: These are often unreliable)."""
    
    @staticmethod
    def fetch_free_proxies() -> List[str]:
        """
        Fetch free proxy list from free-proxy-list.net.
        
        WARNING: Free proxies are often slow, unstable, and may be blocked.
        Consider using paid proxy service for production.
        
        Returns:
            List of proxy URLs
        """
        try:
            # This is a basic example - free proxy lists change frequently
            logger.warning("Fetching from free proxy list - these are unreliable!")
            # Real implementation would scrape the site
            return []
        except Exception as e:
            logger.error(f"Failed to fetch free proxies: {e}")
            return []


def setup_proxy_recommended():
    """
    Print recommended proxy setup instructions.
    """
    instructions = """
PROXY SETUP RECOMMENDATIONS
===========================

For respectful web scraping, proxies can help rotate IPs. However:

FREE PROXIES (Not Recommended):
- Often blocked by target sites
- Slow and unreliable
- High latency
- May themselves be honeypots

PAID PROXY SERVICES (Recommended):
1. ProxyMesh (https://proxymesh.com/)
   - ~$99/month for 10Mbps residential proxies
   - Format: http://[USER]:change-me@[GATE]:[PORT]

2. Bright Data / Luminati (https://brightdata.com/)
   - Residential proxies (most legitimate)
   - Enterprise pricing

3. Smartproxy (https://smartproxy.com/)
   - Affordable residential proxies
   - Good for light scraping

4. Oxylabs (https://oxylabs.io/)
   - Enterprise-grade proxies
   - High-quality residential IPs

ALTERNATIVE: Rotate via Mobile Hotspot
- Use your phone's hotspot as a "rotating proxy"
- Each reconnection gets a new mobile IP
- Free and legitimate
- Recommended for light scraping!

SETUP METHOD:
1. If using paid proxies, set environment variable:
   export SCRAPER_PROXIES="http://proxy1:port,http://proxy2:port"

2. Or create proxies.json:
   {
     "proxies": [
       "http://proxy1:port",
       "http://proxy2:port"
     ]
   }

3. Enable in scraper:
   - Set USE_ROTATING_PROXY = True in configs
   - Or pass use_proxy=True to scraper

RESPECT THE SITES:
- 10+ second delays between requests ✓
- Staggered scraping throughout day ✓
- Limiting scrape frequency ✓
- Consider contacting site owners for API access
"""
    print(instructions)


if __name__ == '__main__':
    setup_proxy_recommended()
