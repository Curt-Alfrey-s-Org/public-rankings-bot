"""
WPA Artistic Pool association rankings — dedicated entrypoint (shared WPA parser).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scrapers.wpa_scraper import WPAScraper


def scrape_wpa_artistic_rankings() -> Optional[List[Dict[str, Any]]]:
    return WPAScraper().scrape_rankings(division="Artistic")
