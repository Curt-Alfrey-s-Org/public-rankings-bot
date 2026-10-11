"""
WPBA association rankings — dedicated scraper entrypoint (PDF via WPBAScraper).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scrapers.wpba_scraper import WPBAScraper


def scrape_wpba_rankings() -> Optional[List[Dict[str, Any]]]:
    """Scrape current WPBA women’s tour points (default PDF source)."""
    return WPBAScraper().scrape_rankings()
